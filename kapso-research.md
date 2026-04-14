# Kapso WhatsApp API - Research

## Que es Kapso

Kapso es "the WhatsApp API for developers". Provee acceso programatico a WhatsApp messaging via REST API, TypeScript SDK, CLI y Webhooks.

---

## URLs Base

| Servicio | Base URL |
|----------|----------|
| WhatsApp (Meta proxy) | `https://api.kapso.ai/meta/whatsapp/v24.0` |
| Platform API | `https://api.kapso.ai/platform/v1` |

---

## Autenticacion

Dos metodos soportados:

1. **API Key Header (recomendado)**: `X-API-Key: your_project_api_key`
2. **Bearer Token**: `Authorization: Bearer your_access_token`

La API key se crea desde el dashboard de Kapso: Sidebar > API keys.

---

## Sandbox

- Entorno de prueba sin credenciales de produccion
- El usuario registra su telefono, recibe un codigo de activacion de 6 caracteres, y lo envia al numero sandbox
- Soporta mensajes de texto e interactivos
- **NO soporta**: templates, template sync, ni multi-recipient
- Puede rutear a agents, flows con inbound triggers, o webhooks

---

## Endpoints Principales

### Enviar Mensaje de Texto

```
POST https://api.kapso.ai/meta/whatsapp/v24.0/{phone_number_id}/messages
```

**Headers:**
```
X-API-Key: YOUR_API_KEY
Content-Type: application/json
```

**Body:**
```json
{
  "messaging_product": "whatsapp",
  "to": "5491112345678",
  "type": "text",
  "text": {
    "body": "Hola! Este es un mensaje de prueba."
  }
}
```

**Nota:** Mensajes no-template solo se pueden enviar dentro de la ventana de 24 horas de conversacion.

### Listar Phone Numbers

```
GET https://api.kapso.ai/platform/v1/whatsapp/phone_numbers
```

**Headers:**
```
X-API-Key: YOUR_API_KEY
```

Soporta filtros: `phone_number_id`, `business_account_id`, `customer_id`, `messaging_enabled`, `name_contains`, rango de fechas, paginacion.

### Crear Webhook

```
POST https://api.kapso.ai/platform/v1/whatsapp/webhooks
```

**Body (Kapso webhook):**
```json
{
  "kind": "kapso",
  "url": "https://your-server.com/webhook",
  "events": ["whatsapp.message.received"],
  "secret_key": "your_secret",
  "active": true,
  "phone_number_id": "optional_for_number_scoped"
}
```

Dos scopes disponibles:
- **Project-scoped**: Omitir `phone_number_id` (recibe eventos de todos los numeros)
- **Number-scoped**: Incluir `phone_number_id` (solo eventos de ese numero)

Dos tipos:
- **`kapso`**: Event-based con buffering y payloads estructurados
- **`meta`**: Raw Meta payloads sin modificar (solo 1 por phone number)

---

## Eventos Webhook

| Evento | Descripcion |
|--------|-------------|
| `whatsapp.message.received` | Mensaje entrante del cliente |
| `whatsapp.message.sent` | Confirmacion de mensaje saliente |
| `whatsapp.message.delivered` | Confirmacion de entrega |
| `whatsapp.message.read` | Read receipt |
| `whatsapp.conversation.created` | Nueva conversacion |
| `whatsapp.conversation.ended` | Conversacion cerrada |
| `whatsapp.conversation.inactive` | Inactividad prolongada |

---

## Seguridad Webhook - Verificacion de Firma

Kapso firma los webhooks con HMAC-SHA256. Verificar usando:

- Header: `X-Webhook-Signature`
- Computar HMAC-SHA256 del body JSON con tu `secret_key`
- Comparar usando timing-safe equal

**Headers incluidos en webhooks Kapso:**
- `X-Webhook-Event`
- `X-Webhook-Signature`
- `X-Idempotency-Key`
- `X-Webhook-Payload-Version: v2`
- En batch: `X-Webhook-Batch` y `X-Batch-Size`

---

## Tipos de Mensaje Soportados

- Text
- Image
- Video
- Audio
- Document
- Sticker
- Location
- Contacts
- Interactive (buttons, lists)
- Template
- Reaction

---

## Otros Endpoints Utiles (Platform API)

| Recurso | Metodo | Path |
|---------|--------|------|
| Listar conversaciones | GET | `/whatsapp/conversations` |
| Listar mensajes | GET | `/whatsapp/messages` |
| Crear contacto | POST | `/whatsapp/contacts` |
| Obtener contacto | GET | `/whatsapp/contacts/{id}` |
| Listar broadcasts | GET | `/whatsapp/broadcasts` |
| Crear broadcast | POST | `/whatsapp/broadcasts` |
| Upload media | POST | `/whatsapp/media` |

---

## Retry Policy (Webhooks)

Reintentos en caso de fallo: 10s, 40s, 90s (~2.5 min total). Despues de agotar reintentos, mensajes batch se convierten a intentos individuales.

---

## CLI (Referencia)

```bash
# Instalar
curl -fsSL https://kapso.ai/install.sh | bash

# Setup
kapso setup

# Listar numeros
kapso whatsapp numbers list

# Enviar mensaje
kapso whatsapp messages send --phone-number-id $ID --to "+5491112345678" --text "Hola"

# Crear webhook
kapso whatsapp webhooks new --phone-number-id $ID --url "https://your-server.com/webhook" \
  --event whatsapp.message.received --active

# Output JSON para parsing
kapso whatsapp numbers list --output json
```

---

## Variables de Entorno Necesarias

```bash
KAPSO_API_KEY=your_project_api_key
KAPSO_PHONE_NUMBER_ID=your_phone_number_id
KAPSO_WEBHOOK_SECRET=your_webhook_secret  # para verificar firmas
```

---

## Documentacion

- Docs: https://docs.kapso.ai/docs/introduction
- Full index: https://docs.kapso.ai/llms.txt
- OpenAPI WhatsApp: https://docs.kapso.ai/api/meta/whatsapp/openapi-whatsapp.yaml
- OpenAPI Platform: https://docs.kapso.ai/api/platform/v1/openapi-platform.yaml
- GitHub: https://github.com/gokapso
