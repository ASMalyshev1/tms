variable "yc_token" {
  type        = string
  description = "YC IAM token"
  sensitive   = true
}

variable "cloud_id" {
  type        = string
  description = "YC cloud id"
}

variable "folder_id" {
  type        = string
  description = "YC folder id"
}

variable "default_zone" {
  type        = string
  description = "Default zone"
  default     = "ru-central1-d"
}

variable "public_zone" {
  type        = string
  description = "Имя публичной DNS-зоны"
}

variable "ssh_pub" {
  type        = string
  description = "Содержимое публичного SSH ключа"
}

# Имена субдоменов
variable "name_portal"  { default = "portal"  }
variable "name_grafana" { default = "grafana" }
variable "name_jira"    { default = "jira"    }
variable "name_gitlab"  { default = "gitlab"  }