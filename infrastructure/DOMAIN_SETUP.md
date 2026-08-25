# Alta del dominio zamorave.com

Guía paso a paso para poner el frontend (ya alojado en S3, servido vía
CloudFront) bajo `zamorave.com`. Se divide en dos bloques:

- **Pasos manuales** (1 y 2): no automatizables con SAM/CloudFormation.
  Los ejecutas tú, una sola vez.
- **Pasos automatizados** (3 y 4): ya están en el código
  (`infrastructure/certificate-us-east-1.yaml`,
  `infrastructure/template.yaml`, `infrastructure/deploy.sh`). Solo hay
  que ejecutarlos con los parámetros que salen de los pasos manuales.

Por qué el registro del dominio no se puede meter en el template: no existe
un recurso `AWS::Route53::Domain` en CloudFormation — registrar un dominio
implica una compra real (pago, datos de contacto, aceptar los términos de
ICANN) y AWS lo trata deliberadamente como una acción fuera de
CloudFormation, solo disponible vía consola o `aws route53domains`.

---

## Paso 1 (manual) — Registrar el dominio en Route 53

1. Entra en la consola de AWS → **Route 53 → Registered domains → Register domain**.
2. Busca `zamorave.com` y confirma que está disponible.
3. Precio orientativo: **~13-14 USD/año** para `.com` (se renueva solo cada
   año salvo que lo desactives).
4. Rellena los datos de contacto (registrante/admin/técnico) — puedes usar
   los mismos para los tres. Dado que es una asociación, usa los datos de
   la Asociación de Usuarios de Trenes AVE de Zamora, no datos personales.
5. Activa **"Privacy protection"** (gratis, oculta los datos de contacto
   del WHOIS público) — recomendado.
6. Confirma y paga.
7. AWS envía un email de verificación a la dirección de contacto — hay que
   confirmarlo en **15 días** o el dominio se suspende. La activación en sí
   suele tardar de minutos a un par de horas para `.com`, pero puede
   llegar a las 24-48h.
8. Al completarse el registro, Route 53 **crea automáticamente una Hosted
   Zone pública** para `zamorave.com` con sus propios name servers (NS) ya
   asignados al dominio — no hace falta ningún paso manual adicional de
   NS/delegación, a diferencia de dominios registrados en un registrador
   externo.

## Paso 2 (manual) — Obtener el Hosted Zone Id

Una vez completado el registro:

```bash
aws route53 list-hosted-zones-by-name \
    --dns-name zamorave.com \
    --query "HostedZones[0].Id" \
    --output text
```

Devuelve algo como `/hostedzone/Z0123456ABCDEF`. Te quedas con la parte
después de `/hostedzone/` (`Z0123456ABCDEF`) — es el `HostedZoneId` que
usan los pasos 3 y 4.

---

## Paso 3 (automatizado) — Certificado ACM en us-east-1

CloudFront exige que el certificado exista en `us-east-1`, sea cual sea la
región del resto del stack (este proyecto despliega en `eu-south-2`) — por
eso es un stack CloudFormation separado, `certificate-us-east-1.yaml`.

```bash
aws cloudformation deploy \
    --region us-east-1 \
    --template-file infrastructure/certificate-us-east-1.yaml \
    --stack-name zamora-trains-frontend-cert \
    --parameter-overrides DomainName=zamorave.com HostedZoneId=Z0123456ABCDEF
```

Este comando **sí queda completamente automatizado**: al pasarle el
`HostedZoneId`, CloudFormation crea él solo los registros CNAME de
validación DNS en esa Hosted Zone y espera a que el certificado quede
`ISSUED` (unos minutos) antes de devolver el control. No hace falta ir a
la consola ni copiar registros a mano.

Recupera el ARN del certificado emitido:

```bash
aws cloudformation describe-stacks \
    --region us-east-1 \
    --stack-name zamora-trains-frontend-cert \
    --query "Stacks[0].Outputs[?OutputKey=='CertificateArn'].OutputValue" \
    --output text
```

## Paso 4 (automatizado) — Desplegar el stack principal con el dominio

Con `HostedZoneId` (paso 2) y `CertificateArn` (paso 3) ya en mano:

```bash
./infrastructure/deploy.sh prod \
    --domain zamorave.com \
    --hosted-zone-id Z0123456ABCDEF \
    --certificate-arn arn:aws:acm:us-east-1:XXXXXXXXXX:certificate/XXXXXXXXX
```

Esto despliega (o actualiza) `infrastructure/template.yaml` con:

- `FrontendDistribution` (CloudFront + Origin Access Control) delante del
  bucket S3 del frontend, ahora privado.
- El certificado ACM asociado como `ViewerCertificate` de la distribución.
- Registros `A`/`AAAA` alias en Route 53 para `zamorave.com` y
  `www.zamorave.com` apuntando a la distribución CloudFront.
- Fallback de rutas de la SPA (403/404 → `index.html`).

Después, sube el build del frontend y **invalida la caché de CloudFront**
(ya integrado en el script):

```bash
./infrastructure/deploy_frontend.sh prod
```

## Verificación final

- `https://zamorave.com` y `https://www.zamorave.com` deben responder con
  el frontend y candado válido. La propagación DNS de los registros alias
  suele ser casi inmediata (Route 53 los sirve directamente), pero el
  despliegue de la propia distribución CloudFront a los edge locations
  puede tardar 10-20 minutos tras el `deploy.sh`.
- Si ves un error de certificado en el navegador recién desplegado, espera
  a que CloudFront termine de propagar (`aws cloudfront get-distribution
  --id <FrontendDistributionId> --query "Distribution.Status"` debe decir
  `Deployed`) antes de investigar más.
- El CORS de `TrainsApi` (API de datos) ya está en `AllowOrigins: "*"`, así
  que no hace falta tocarlo al añadir el dominio propio.

## Nota de coste recurrente

- Dominio `.com`: ~13-14 USD/año (renovación automática vía Route 53 salvo
  que la desactives).
- Hosted Zone de Route 53: 0.50 USD/mes.
- CloudFront + ACM: el certificado es gratis; CloudFront tiene capa
  gratuita amplia y, para el tráfico esperado de este proyecto, el coste
  adicional es marginal (céntimos/mes).
