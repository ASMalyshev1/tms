output "portal_public_ip"   { value = yandex_compute_instance.vm_portal.network_interface[0].nat_ip_address }
output "gitlab_public_ip"   { value = yandex_compute_instance.vm_gitlab.network_interface[0].nat_ip_address }
output "grafana_private_ip" { value = yandex_compute_instance.vm_grafana.network_interface[0].ip_address }
output "jira_private_ip"    { value = yandex_compute_instance.vm_jira.network_interface[0].ip_address }

output "public_fqdns" {
  value = {
    portal  = yandex_dns_recordset.pub_portal.name
    grafana = yandex_dns_recordset.pub_grafana.name
    jira    = yandex_dns_recordset.pub_jira.name
    gitlab  = yandex_dns_recordset.pub_gitlab.name
  }
}