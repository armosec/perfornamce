#
# EKS Cluster Resources
#  * IAM Role to allow EKS service to manage other AWS services
#  * EC2 Security Group to allow networking traffic with EKS cluster
#  * EKS Cluster
#  * EKS plugin installation
#

####################################################################
#### IAM Role to allow EKS service to manage other AWS services ####
####################################################################

resource "aws_iam_role" "eks-iam-role" {
  name               = "${local.owner}-eks-iam-role-${local.random}"
  assume_role_policy = <<EOF
{
 "Version": "2012-10-17",
 "Statement": [
  {
   "Effect": "Allow",
   "Principal": {
    "Service": "eks.amazonaws.com"
   },
   "Action": "sts:AssumeRole"
  }
 ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "AmazonEKSClusterPolicy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks-iam-role.name
}

resource "aws_iam_role_policy_attachment" "AmazonEKSVPCResourceController" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController"
  role       = aws_iam_role.eks-iam-role.name
}

###########################################################################
##### EC2 Security Group to allow networking traffic with EKS cluster #####
###########################################################################

resource "aws_security_group" "sg" {
  name        = "${local.cluster_name}-sg"
  description = "Cluster communication with worker nodes"
  vpc_id      = aws_vpc.cluster_vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name  = "${local.cluster_name}-sg"
    Owner = local.owner
  }
}

# resource "aws_security_group_rule" "demo-cluster-ingress-workstation-https" {
#   cidr_blocks       = [local.workstation-external-cidr]
#   description       = "Allow workstation to communicate with the cluster API Server"
#   from_port         = 443
#   protocol          = "tcp"
#   security_group_id = aws_security_group.sg.id
#   to_port           = 443
#   type              = "ingress"
# }

#######################
##### EKS Cluster #####
#######################

resource "aws_eks_cluster" "eks_cluster" {
  name     = local.cluster_name
  role_arn = aws_iam_role.eks-iam-role.arn
  version  = "1.29"
  vpc_config {
    security_group_ids = [aws_security_group.sg.id]
    subnet_ids         = aws_subnet.subnet[*].id
  }

  depends_on = [
    aws_iam_role_policy_attachment.AmazonEKSClusterPolicy,
    aws_iam_role_policy_attachment.AmazonEKSVPCResourceController,
  ]

  tags = {
    Owner = local.owner
    Name  = local.cluster_name
  }
}

###################################
##### EKS plugin installation #####
###################################

resource "aws_eks_addon" "vpc-cni" {
  cluster_name = local.cluster_name
  addon_name   = "vpc-cni"

  depends_on = [
    aws_eks_node_group.worker_node_group_1,
  ]
}

resource "aws_eks_addon" "csi" {
  cluster_name = local.cluster_name
  addon_name   = "aws-ebs-csi-driver"

  depends_on = [
    aws_eks_node_group.worker_node_group_1,
  ]
}

resource "aws_eks_addon" "coredns" {
  cluster_name = local.cluster_name
  addon_name   = "coredns"

  depends_on = [
    aws_eks_node_group.worker_node_group_1,
  ]
}

resource "aws_eks_addon" "kube-proxy" {
  cluster_name = local.cluster_name
  addon_name   = "kube-proxy"

  depends_on = [
    aws_eks_node_group.worker_node_group_1,
  ]
}

data "tls_certificate" "tls" {
  url = aws_eks_cluster.eks_cluster.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "openid" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.tls.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.eks_cluster.identity[0].oidc[0].issuer
}

data "aws_iam_policy_document" "assume_role_policy" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"

    condition {
      test     = "StringEquals"
      variable = "${replace(aws_iam_openid_connect_provider.openid.url, "https://", "")}:sub"
      values   = ["system:serviceaccount:kube-system:ebs-csi-controller-sa"]
    }

    principals {
      identifiers = [aws_iam_openid_connect_provider.openid.arn]
      type        = "Federated"
    }
  }
}

resource "aws_iam_role" "csi-role" {
  assume_role_policy = data.aws_iam_policy_document.assume_role_policy.json
  name               = "csi-role-${local.random}"
}

resource "aws_iam_role_policy_attachment" "csi-role-attachment" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
  role       = aws_iam_role.csi-role.name
}

# module "aws_ebs_csi_driver" {
#   source                           = "github.com/andreswebs/terraform-aws-eks-ebs-csi-driver"
#   cluster_name                     = local.cluster_name
#   cluster_oidc_provider            = "${replace(aws_iam_openid_connect_provider.openid.url, "https://", "")}"
#   iam_role_name                    = aws_iam_role.csi-role.name
#   # chart_version_aws_ebs_csi_driver = var.chart_version_aws_ebs_csi_driver

#   depends_on = [
#     aws_eks_node_group.worker_node_group_1,
#   ]
# }