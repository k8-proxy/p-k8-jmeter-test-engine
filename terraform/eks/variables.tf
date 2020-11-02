variable "region" {
  description = "AWS region"
}


variable m4_x_spot_price {
  type        = map
  description = "Spot Instance price based on region"
  default = {
    us-west-1 = "0.080"
    eu-west-1 = "0.289"
  }
}

variable m4_2x_spot_price {
  type        = map
  description = "Spot Instance price based on region"
  default = {
    us-west-1 = "0.140"
    eu-west-1 = "0.569"
  }
}

variable cluster_config {
  type    = string
  default = "aws eks --region us-west-1 update-kubeconfig --name glasswall-test-cluster"
}


variable common_resources {
  type = string
  default = "kubectl create serviceaccount --namespace kube-system tiller ;kubectl create clusterrolebinding tiller-cluster-rule --clusterrole=cluster-admin --serviceaccount=kube-system:tiller ; sleep 10 ; kubectl patch deploy --namespace kube-system tiller-deploy -p '{\"spec\":{\"template\":{\"spec\":{\"serviceAccount\":\"tiller\"}}}}' ;sleep 10 ;helm init --service-account tiller --upgrade \n"
}

variable common_chart {
  type = string
  default = "sleep 40 ; helm upgrade --install common --namespace=common ~/Downloads/p-k8-jmeter-test-engine/helm-charts/common-resources/ -f ~/Downloads/p-k8-jmeter-test-engine/helm-charts/common-resources/aws.yaml"
}

variable cluster_interpreter {
  type    = list(string)
  default = ["/bin/sh", "-c"]
}