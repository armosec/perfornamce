subscription_id = "05fed2cc-041d-4c53-b4b8-a1aa128d189f" ## Azure subscription ID that you have permmsion to use
cluster_owner   = "<YOUR_NAME_HERE>"                                ## Cluster owner name
location        = "North Europe"                         ## Rsource group and AKS cluster region                 
node_count      = 3                                      ## Worker node number
machine_type    = "Standard_B2ms"                        ## Machine type for AKS worker nodes
zones           = ["1", "2", "3"]                        ## The availiabilty zones - type: list(strings)

# resource_group_name = 
# variable = 
# key_vault_firewall_bypass_ip_cidr = 
# managed_identity_principal_id = 