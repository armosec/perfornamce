variable "region" {
  default = "eu-west-2" # London
}

variable "owner" {
  default = "performance"
  type    = string
}

variable "desired_size" {
  default = 2
  type    = number
}

variable "max_size" {
  default = 300
  type    = number
}

variable "subnet_count" {
  default = 2
  type    = number
}

variable "instance_types" {
  default = "m5.xlarge"
  type    = string
}

# variable "cluster_name" {
#   default = "${var.owner}-test-cluster-${random_string.string.id}"
#   type    = string
# }

# variable "vpc_name" {
#   default = "${var.owner}-vpc-${random_string.string.id}"
#   type    = string
# }
