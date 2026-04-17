{{/*
UI renderer — produces Deployment, Service, Ingress/IngressRoute, HPA, PDB for
a single UI. Invoked by ui/deployments.yaml once per UI (desk/ops/client).

Usage:
  {{ include "mini-hedge.ui.render" (dict "root" . "ui" $uiSpec "defaults" $defaults) }}

`$uiSpec`  — one of .Values.uis.{desk,ops,client}
`$defaults` — .Values.uis.defaults (merged via mergeOverwrite at call site)
*/}}
{{- define "mini-hedge.ui.render" -}}
{{- $root := .root -}}
{{- $ui := .ui -}}
{{- $d := .defaults -}}
{{- $name := include "mini-hedge.ui.fullname" (dict "root" $root "ui" $ui) -}}
{{- $image := include "mini-hedge.ui.image" (dict "root" $root "ui" $ui) -}}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ $name }}
  labels:
    {{- include "mini-hedge.ui.labels" (dict "root" $root "ui" $ui) | nindent 4 }}
spec:
  {{- if not $d.autoscaling.enabled }}
  replicas: {{ $d.replicaCount }}
  {{- end }}
  revisionHistoryLimit: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 0
  selector:
    matchLabels:
      {{- include "mini-hedge.ui.selectorLabels" (dict "root" $root "ui" $ui) | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "mini-hedge.ui.selectorLabels" (dict "root" $root "ui" $ui) | nindent 8 }}
    spec:
      serviceAccountName: {{ include "mini-hedge.serviceAccountName" $root }}
      {{- with $root.Values.global.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      securityContext:
        {{- toYaml $d.podSecurityContext | nindent 8 }}
      terminationGracePeriodSeconds: 30
      containers:
        - name: {{ $ui.name }}
          image: {{ $image }}
          imagePullPolicy: {{ $d.image.pullPolicy }}
          securityContext:
            {{- toYaml $d.containerSecurityContext | nindent 12 }}
          ports:
            - name: http
              containerPort: {{ $ui.containerPort }}
              protocol: TCP
          env:
            - name: NODE_ENV
              value: production
            - name: HOSTNAME
              value: "0.0.0.0"
            {{- range $k, $v := $ui.env }}
            - name: {{ $k }}
              value: {{ $v | quote }}
            {{- end }}
          livenessProbe:
            httpGet:
              path: {{ $d.probes.liveness.path }}
              port: http
            initialDelaySeconds: {{ $d.probes.liveness.initialDelaySeconds }}
            periodSeconds: {{ $d.probes.liveness.periodSeconds }}
          readinessProbe:
            httpGet:
              path: {{ $d.probes.readiness.path }}
              port: http
            initialDelaySeconds: {{ $d.probes.readiness.initialDelaySeconds }}
            periodSeconds: {{ $d.probes.readiness.periodSeconds }}
          resources:
            {{- toYaml $d.resources | nindent 12 }}
          {{- with $d.extraVolumeMounts }}
          volumeMounts:
            {{- toYaml . | nindent 12 }}
          {{- end }}
      {{- with $d.extraVolumes }}
      volumes:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              {{- include "mini-hedge.ui.selectorLabels" (dict "root" $root "ui" $ui) | nindent 14 }}
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchLabels:
                    {{- include "mini-hedge.ui.selectorLabels" (dict "root" $root "ui" $ui) | nindent 20 }}
                topologyKey: kubernetes.io/hostname
---
apiVersion: v1
kind: Service
metadata:
  name: {{ $name }}
  labels:
    {{- include "mini-hedge.ui.labels" (dict "root" $root "ui" $ui) | nindent 4 }}
spec:
  type: {{ $d.service.type }}
  ports:
    - name: http
      port: {{ $ui.servicePort }}
      targetPort: http
      protocol: TCP
  selector:
    {{- include "mini-hedge.ui.selectorLabels" (dict "root" $root "ui" $ui) | nindent 4 }}
{{- if $d.autoscaling.enabled }}
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ $name }}
  labels:
    {{- include "mini-hedge.ui.labels" (dict "root" $root "ui" $ui) | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ $name }}
  minReplicas: {{ $d.autoscaling.minReplicas }}
  maxReplicas: {{ $d.autoscaling.maxReplicas }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ $d.autoscaling.targetCPUUtilizationPercentage }}
{{- end }}
{{- if $d.podDisruptionBudget.enabled }}
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ $name }}
  labels:
    {{- include "mini-hedge.ui.labels" (dict "root" $root "ui" $ui) | nindent 4 }}
spec:
  minAvailable: {{ $d.podDisruptionBudget.minAvailable }}
  selector:
    matchLabels:
      {{- include "mini-hedge.ui.selectorLabels" (dict "root" $root "ui" $ui) | nindent 6 }}
{{- end }}
{{- if $d.ingress.enabled }}
---
{{- if $d.ingress.useIngressRoute }}
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: {{ $name }}
  labels:
    {{- include "mini-hedge.ui.labels" (dict "root" $root "ui" $ui) | nindent 4 }}
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`{{ $ui.host }}`)
      kind: Rule
      services:
        - name: {{ $name }}
          port: {{ $ui.servicePort }}
  {{- if $d.ingress.tls.enabled }}
  tls:
    secretName: {{ $ui.tlsSecretName }}
  {{- end }}
{{- else }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ $name }}
  labels:
    {{- include "mini-hedge.ui.labels" (dict "root" $root "ui" $ui) | nindent 4 }}
spec:
  ingressClassName: {{ $d.ingress.className }}
  {{- if $d.ingress.tls.enabled }}
  tls:
    - hosts:
        - {{ $ui.host }}
      secretName: {{ $ui.tlsSecretName }}
  {{- end }}
  rules:
    - host: {{ $ui.host }}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {{ $name }}
                port:
                  number: {{ $ui.servicePort }}
{{- end }}
{{- end }}
{{- end -}}
