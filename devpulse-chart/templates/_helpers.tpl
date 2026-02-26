{{/*
Expand the name of the chart.
*/}}
{{- define "devpulse.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "devpulse.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "devpulse.labels" -}}
helm.sh/chart: {{ include "devpulse.chart" . }}
{{ include "devpulse.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Values.managedBy | default .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "devpulse.selectorLabels" -}}
app.kubernetes.io/name: {{ include "devpulse.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
