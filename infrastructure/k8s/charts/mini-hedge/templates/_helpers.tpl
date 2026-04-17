{{/* ───────────────────────── Standard Helm helpers ───────────────────────── */}}

{{- define "mini-hedge.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "mini-hedge.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "mini-hedge.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "mini-hedge.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "mini-hedge.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/* Common labels applied to every resource. */}}
{{- define "mini-hedge.labels" -}}
helm.sh/chart: {{ include "mini-hedge.chart" . }}
app.kubernetes.io/name: {{ include "mini-hedge.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/part-of: mini-hedge
environment: {{ .Values.global.environment | quote }}
{{- end -}}

{{/* Selector labels (immutable — never add chart version/env here). */}}
{{- define "mini-hedge.selectorLabels" -}}
app.kubernetes.io/name: {{ include "mini-hedge.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/* ───────────────────────── Backend helpers ──────────────────────────── */}}

{{- define "mini-hedge.backend.fullname" -}}
{{- printf "%s-backend" (include "mini-hedge.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "mini-hedge.backend.image" -}}
{{- $tag := .Values.backend.image.tag | default .Chart.AppVersion -}}
{{- printf "%s/%s:%s" .Values.global.imageRegistry .Values.backend.image.repository $tag -}}
{{- end -}}

{{- define "mini-hedge.backend.labels" -}}
{{ include "mini-hedge.labels" . }}
app.kubernetes.io/component: backend
{{- end -}}

{{- define "mini-hedge.backend.selectorLabels" -}}
{{ include "mini-hedge.selectorLabels" . }}
app.kubernetes.io/component: backend
{{- end -}}

{{/* ───────────────────────── UI helpers ───────────────────────────────── */}}

{{/*
Render a UI deployment/service by merging `.Values.uis.defaults` with a named
UI spec. Usage:
  {{- include "mini-hedge.ui.fullname" (dict "root" . "ui" .Values.uis.desk) }}
*/}}
{{- define "mini-hedge.ui.fullname" -}}
{{- printf "%s-%s" (include "mini-hedge.fullname" .root) .ui.name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "mini-hedge.ui.image" -}}
{{- $tag := .ui.image.tag | default .root.Chart.AppVersion -}}
{{- printf "%s/%s:%s" .root.Values.global.imageRegistry .ui.image.repository $tag -}}
{{- end -}}

{{- define "mini-hedge.ui.labels" -}}
{{ include "mini-hedge.labels" .root }}
app.kubernetes.io/component: {{ .ui.name }}
{{- end -}}

{{- define "mini-hedge.ui.selectorLabels" -}}
{{ include "mini-hedge.selectorLabels" .root }}
app.kubernetes.io/component: {{ .ui.name }}
{{- end -}}

{{/* ───────────────────────── Migrations helpers ───────────────────────── */}}

{{- define "mini-hedge.migrations.fullname" -}}
{{- printf "%s-migrate" (include "mini-hedge.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "mini-hedge.migrations.image" -}}
{{- $tag := .Values.migrations.image.tag | default .Chart.AppVersion -}}
{{- printf "%s/%s:%s" .Values.global.imageRegistry .Values.migrations.image.repository $tag -}}
{{- end -}}
