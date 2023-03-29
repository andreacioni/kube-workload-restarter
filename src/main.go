package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/robfig/cron"
	v1 "k8s.io/api/apps/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
	"k8s.io/client-go/util/homedir"

	_ "k8s.io/client-go/plugin/pkg/client/auth"
)

const (
	RESTART_AFTER_ANNOTATION = "restarter/after"
	RESTART_WHEN_ANNOTATION  = "restarter/when"
)

var (
	clientset     *kubernetes.Clientset
	configuration Config
)

type Config struct {
	Kubeconfig      string
	Namespace       string
	LoopDurationSec int64
	Verbose         bool
}

func main() {
	configuration = ParseConfig()

	var err error

	if clientset, err = buildInsideClusterClient(configuration); err != nil {
		log.Printf("failed to build inside-cluster client: %v", err)
		log.Printf("trying to build outside-cluster-one...")
		err = nil

		if clientset, err = buildOutsideClusterClient(configuration); err != nil {
			log.Fatal("failed to build outside-cluster client: %w", err)
		}
	}

	for {
		deployments, err := getNamespacedDeployments(configuration.Namespace)
		if err != nil {
			log.Fatal("failed to retrieve the deployment list: %w", err)
		}
		log.Printf("there are %d deployment in namespace: %s", len(deployments.Items), configuration.Namespace)

		list := deployments.Items
		for _, d := range list {
			if err := handleDeployment(d); err != nil {
				fmt.Println(err)
			}
		}

		time.Sleep(time.Duration(configuration.LoopDurationSec) * time.Second)
	}
}

func handleDeployment(deployment v1.Deployment) error {
	name := deployment.Name
	restartAfter := deployment.Annotations[RESTART_AFTER_ANNOTATION]

	if restartAfter != "" {
		log.Printf("[%s] restart annotation found: %s", name, restartAfter)

		var restartAfterSec int64
		var deploymentLifeTime int64
		var err error
		restartWhenMatch := false

		if restartWhenCron, ok := deployment.Annotations[RESTART_WHEN_ANNOTATION]; ok {
			restartWhenMatch, err = evaluateCronExpression(restartWhenCron)

			if err != nil {
				log.Printf("[%s] has %s annotation but it can't be parsed: '%s'", name, RESTART_WHEN_ANNOTATION, restartWhenCron)
			}
		}

		if restartAfterSec, err = parseRestartAfter(restartAfter); err != nil {
			return fmt.Errorf("[%s] failed to parse '%s' duration on deployment: %s, error: %v", name, restartAfter, name, err)
		}

		if deploymentLifeTime, err = evaluateDeploymentLifetime(deployment); err != nil {
			return fmt.Errorf("[%s] failed to evaluate deployment lifetime: %v", name, err)
		}

		if deploymentLifeTime > restartAfterSec && restartWhenMatch {
			log.Printf("[%s] need to be restarted (%ds > %ds)", name, deploymentLifeTime, restartAfterSec)
			if err = restartDeployment(deployment); err != nil {
				return fmt.Errorf("[%s] failed to be restarted: %v", name, err)
			}
			log.Printf("[%s] has been restarted", name)
		}
	}

	return nil
}

func restartDeployment(deployment v1.Deployment) error {
	annotationMap := deployment.Spec.Template.Annotations
	if annotationMap == nil {
		annotationMap = map[string]string{}
	}
	annotationMap["kubectl.kubernetes.io/restartedAt"] = time.Now().Local().String()
	deployment.Spec.Template.Annotations = annotationMap

	_, err := clientset.AppsV1().Deployments(configuration.Namespace).Update(context.TODO(), &deployment, metav1.UpdateOptions{})

	return err
}

func mapToString(m map[string]string) string {
	var sb strings.Builder

	for k, v := range m {
		sb.WriteString(k)
		sb.WriteString("=")
		sb.WriteString(v)
		sb.WriteString(",")
	}

	result := sb.String()
	if len(result) > 0 {
		result = result[:len(result)-1] // Remove the last comma
	}

	return fmt.Sprint(result) // Output: key1=value1,key2=value2,key3=value3
}

func evaluateDeploymentLifetime(deployment v1.Deployment) (int64, error) {
	var replicaSet v1.ReplicaSet
	var err error

	if replicaSet, err = getMostRecentReplicaset(deployment); err != nil {
		return 0, err
	}

	log.Printf("[%s] most recent replicaset is: %s (created at: %s)", deployment.Name, replicaSet.Name, replicaSet.CreationTimestamp)

	return time.Now().UTC().Unix() - replicaSet.CreationTimestamp.Unix(), nil
}

func getMostRecentReplicaset(deployment v1.Deployment) (v1.ReplicaSet, error) {
	selectors := deployment.Spec.Selector.MatchLabels
	selectorsStr := mapToString(selectors)

	replicasets, err := clientset.AppsV1().ReplicaSets(configuration.Namespace).List(context.TODO(), metav1.ListOptions{LabelSelector: selectorsStr})

	if err != nil {
		return v1.ReplicaSet{}, err
	}

	log.Printf("[%s] found %d replicas", deployment.Name, len(replicasets.Items))

	replicaSetList := replicasets.Items
	if err = ensureSingleActiveReplicaset(replicaSetList); err != nil {
		return v1.ReplicaSet{}, err
	}

	sort.Slice(replicaSetList, func(i, j int) bool {
		return replicaSetList[i].CreationTimestamp.Before(&replicaSetList[j].CreationTimestamp)
	})

	return replicaSetList[len(replicaSetList)-1], nil
}

func ensureSingleActiveReplicaset(replicaSetList []v1.ReplicaSet) error {
	activeReplicasets := 0
	for _, v := range replicaSetList {
		if v.Status.Replicas != 0 {
			activeReplicasets++
		}
	}

	if activeReplicasets > 1 {
		return fmt.Errorf("multiple active replicaset found")
	}

	return nil
}

func parseRestartAfter(restartAfterStr string) (int64, error) {
	duration, err := time.ParseDuration(restartAfterStr)

	if err != nil {
		return 0, err
	}

	return int64(duration.Seconds()), nil
}

func buildOutsideClusterClient(cfg Config) (*kubernetes.Clientset, error) {
	// use the current context in kubeconfig
	config, err := clientcmd.BuildConfigFromFlags("", cfg.Kubeconfig)
	if err != nil {
		return nil, err
	}

	// create the clientset
	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		return nil, err
	}

	return clientset, nil
}

func buildInsideClusterClient(cfg Config) (*kubernetes.Clientset, error) {

	config, err := rest.InClusterConfig()
	if err != nil {
		return nil, err
	}

	// create the clientset
	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		return nil, err
	}

	return clientset, nil
}

func getNamespacedDeployments(namespace string) (*v1.DeploymentList, error) {
	deployments, err := clientset.AppsV1().Deployments(namespace).List(context.TODO(), metav1.ListOptions{})
	return deployments, err
}

func ParseConfig() Config {
	c := Config{
		Kubeconfig:      filepath.Join(homedir.HomeDir(), ".kube", "config"),
		Namespace:       "default",
		LoopDurationSec: 30,
	}

	if kubeconfig := os.Getenv("K8S_RST_KUBECONFG"); kubeconfig != "" {
		c.Kubeconfig = kubeconfig
	}

	if namespace := os.Getenv("K8S_RST_NAMESPACE"); namespace != "" {
		c.Namespace = namespace
	}

	if duration := os.Getenv("K8S_RST_LOOPDURATION"); duration != "" {
		if intDuration, err := strconv.ParseInt(duration, 10, 64); err == nil {
			c.LoopDurationSec = intDuration
		}
	}

	if verbose := os.Getenv("K8S_RST_VERBOSE"); verbose != "" {
		if verboseBool, err := strconv.ParseBool(verbose); err == nil {
			c.Verbose = verboseBool
		}
	}

	return c

}

func evaluateCronExpression(cronExpr string) (bool, error) {
	p, err := cron.ParseStandard(cronExpr)
	if err != nil {
		return false, err
	}
	now := time.Now()
	nextTime := p.Next(now)
	return now.Equal(nextTime), nil
}
