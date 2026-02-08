{{/*
Common labels
*/}}
{{- define "spiderfoot.labels" -}}
app.kubernetes.io/name: {{ include "spiderfoot.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ include "spiderfoot.chart" . }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "spiderfoot.selectorLabels" -}}
app.kubernetes.io/name: {{ include "spiderfoot.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Chart name
*/}}
{{- define "spiderfoot.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Full name
*/}}
{{- define "spiderfoot.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Chart label
*/}}
{{- define "spiderfoot.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Service account name
*/}}
{{- define "spiderfoot.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "spiderfoot.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
PostgreSQL host
*/}}
{{- define "spiderfoot.postgresql.host" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "%s-postgresql" (include "spiderfoot.fullname" .) }}
{{- else }}
{{- .Values.postgresql.external.host }}
{{- end }}
{{- end }}

{{/*
Redis host
*/}}
{{- define "spiderfoot.redis.host" -}}
{{- if .Values.redis.enabled }}
{{- printf "%s-redis-master" (include "spiderfoot.fullname" .) }}
{{- else }}
{{- .Values.redis.external.host }}
{{- end }}
{{- end }}

{{/*
Common environment variables
*/}}
{{- define "spiderfoot.env" -}}
- name: SF_DEPLOY_MODE
  value: "microservices"
- name: SF_LOG_LEVEL
  value: {{ .Values.config.logLevel | quote }}
- name: SF_STRUCTURED_LOGGING
  value: {{ .Values.config.structuredLogging | quote }}
- name: SF_EVENTBUS_BACKEND
  value: {{ .Values.config.eventBusBackend | quote }}
- name: SF_CACHE_BACKEND
  value: {{ .Values.config.cacheBackend | quote }}
- name: SF_AUTH_METHOD
  value: {{ .Values.config.authMethod | quote }}
{{- if .Values.postgresql.enabled }}
- name: SF_DB_TYPE
  value: "postgresql"
- name: SF_DB_HOST
  value: {{ include "spiderfoot.postgresql.host" . | quote }}
- name: SF_DB_PORT
  value: "5432"
- name: SF_DB_NAME
  value: {{ .Values.postgresql.auth.database | quote }}
- name: SF_DB_USER
  value: {{ .Values.postgresql.auth.username | quote }}
- name: SF_DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "spiderfoot.fullname" . }}-db
      key: password
{{- end }}
{{- if .Values.redis.enabled }}
- name: SF_REDIS_HOST
  value: {{ include "spiderfoot.redis.host" . | quote }}
- name: SF_REDIS_PORT
  value: "6379"
{{- end }}
{{- if .Values.config.jwtSecret }}
- name: SF_JWT_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ include "spiderfoot.fullname" . }}-auth
      key: jwt-secret
{{- end }}
{{- end }}
