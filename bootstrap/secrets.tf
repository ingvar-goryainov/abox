resource "kubectl_manifest" "kagent_namespace" {
  count = var.google_api_key != "" ? 1 : 0

  depends_on = [terraform_data.cluster]

  yaml_body = <<-YAML
    apiVersion: v1
    kind: Namespace
    metadata:
      name: kagent
  YAML
}

resource "kubernetes_secret_v1" "kagent_gemini" {
  count = var.google_api_key != "" ? 1 : 0

  depends_on = [kubectl_manifest.kagent_namespace]

  metadata {
    name      = "kagent-gemini"
    namespace = "kagent"
  }

  data_wo = {
    GOOGLE_API_KEY = var.google_api_key
  }
  data_wo_revision = var.google_api_key_revision
}
