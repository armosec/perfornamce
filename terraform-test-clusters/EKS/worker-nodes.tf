#
# EKS Worker Nodes Resources
#  * IAM role allowing Kubernetes actions to access other AWS services
#  * EKS Node Group to launch worker nodes
#

###########################################################################
#### IAM role allowing Kubernetes actions to access other AWS services ####
###########################################################################

resource "aws_iam_role" "workernodes" {
  name = "${local.owner}-eks-node-group-role-${random_string.suffix.id}"

  assume_role_policy = jsonencode({
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
    Version = "2012-10-17"
  })
}

resource "aws_iam_role_policy_attachment" "AmazonEKSWorkerNodePolicy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.workernodes.name
}

resource "aws_iam_role_policy_attachment" "AmazonEKS_CNI_Policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.workernodes.name
}

resource "aws_iam_role_policy_attachment" "EC2InstanceProfileForImageBuilderECRContainerBuilds" {
  policy_arn = "arn:aws:iam::aws:policy/EC2InstanceProfileForImageBuilderECRContainerBuilds"
  role       = aws_iam_role.workernodes.name
}

resource "aws_iam_role_policy_attachment" "AmazonEC2ContainerRegistryReadOnly" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.workernodes.name
}

resource "aws_iam_role_policy_attachment" "AmazonEBSCSIDriverPolicy" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
  role       = aws_iam_role.workernodes.name
}

##########################
##### EKS Node Group #####
##########################

resource "aws_eks_node_group" "worker_node_group_1" {
  cluster_name = local.cluster_name
  # node_group_name = "node-group-1"
  node_group_name_prefix = "node-group-"
  node_role_arn          = aws_iam_role.workernodes.arn
  subnet_ids             = aws_subnet.subnet[*].id
  instance_types         = ["${var.instance_types}"]

  scaling_config {
    desired_size = var.desired_size
    max_size     = var.max_size
    min_size     = 0
  }

  depends_on = [
    aws_iam_role_policy_attachment.AmazonEKSWorkerNodePolicy,
    aws_iam_role_policy_attachment.AmazonEKS_CNI_Policy,
    aws_iam_role_policy_attachment.AmazonEC2ContainerRegistryReadOnly,
    aws_iam_role_policy_attachment.EC2InstanceProfileForImageBuilderECRContainerBuilds,
    aws_iam_role_policy_attachment.AmazonEBSCSIDriverPolicy,
    aws_eks_cluster.eks_cluster,
  ]

  tags = {
    Owner = local.owner
    Name  = local.cluster_name
  }

  lifecycle {
    create_before_destroy = true
    # ignore_changes = [scaling_config]
  }
}