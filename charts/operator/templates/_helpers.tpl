{{/*
Expand the name of the chart.
*/}}
{{- define "azimuth-schedule-operator.name" -}}
{{- .Chart.Name | lower | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "azimuth-schedule-operator.fullname" -}}
{{- if contains .Chart.Name .Release.Name }}
{{- .Release.Name | lower | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name .Chart.Name | lower | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "azimuth-schedule-operator.chart" -}}
{{-
  printf "%s-%s" .Chart.Name .Chart.Version |
    replace "+" "_" |
    trunc 63 |
    trimSuffix "-" |
    trimSuffix "." |
    trimSuffix "_"
}}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "azimuth-schedule-operator.selectorLabels" -}}
app.kubernetes.io/name: {{ include "azimuth-schedule-operator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "azimuth-schedule-operator.labels" -}}
helm.sh/chart: {{ include "azimuth-schedule-operator.chart" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
{{ include "azimuth-schedule-operator.selectorLabels" . }}
{{- end }}

{{/*
Produces the metadata for a CRD.
*/}}
{{- define "azimuth-schedule-operator.crd.metadata" }}
metadata:
  labels: {{ include "azimuth-schedule-operator.labels" . | nindent 4 }}
  {{- if .Values.crds.keep }}
  annotations:
    helm.sh/resource-policy: keep
  {{- end }}
{{- end }}

{{/*
Loads a CRD from the specified file and merges in the metadata.
*/}}
{{- define "azimuth-schedule-operator.crd" }}
{{- $ctx := index . 0 }}
{{- $path := index . 1 }}
{{- $crd := $ctx.Files.Get $path | fromYaml }}
{{- $metadata := include "azimuth-schedule-operator.crd.metadata" $ctx | fromYaml }}
{{- merge $crd $metadata | toYaml }}
{{- end }}
