# Proximos pasos — Estado actual y trabajo pendiente

## Resumen de estado

| Modulo | Completado | Pendiente |
|--------|-----------|-----------|
| Zona compartida (setup, Docker, Kapso, webhook) | 100% | — |
| Grupo A — Onboarding (backend + frontend) | ~95% | Polish frontend, endpoint faltante |
| Grupo B — Publicacion (backend + frontend) | ~60% | Flujo bot, categorias, imagenes, polish frontend |

---

## PRIORIDAD 1 — Grupo B: Flujo de publicacion por bot

**Problema**: un usuario que completo onboarding y escribe "publicar" solo recibe el primer prompt pero no hay logica para seguir el flujo paso a paso. `publication/service.py` > `process_message()` tiene un TODO.

### Tareas

1. **Crear modelo `PublicationSession`** en `backend/app/publication/models.py`
   - Similar a `OnboardingSession` del Grupo A
   - Campos: `id`, `user_id` (FK), `current_step`, `data` (JSON), `completed` (bool), `created_at`
   - Este modelo persiste el estado del flujo conversacional

2. **Implementar `process_message()` completo** en `backend/app/publication/service.py`
   - Recorrer los 5 pasos definidos en `PUBLICATION_STEPS`:
     - Paso 0: categoria (el usuario elige 1-4)
     - Paso 1: titulo
     - Paso 2: descripcion/body
     - Paso 3: foto (o "omitir")
     - Paso 4: confirmacion (si/no)
   - Guardar respuesta de cada paso en `PublicationSession.data`
   - Al confirmar, llamar a `create_publication()` con los datos acumulados
   - Referencia: mirar como lo hace `onboarding/service.py` > `process_step()`

3. **Generar migracion** para la nueva tabla:
   ```bash
   docker compose exec backend alembic revision --autogenerate -m "b_001_add_publication_sessions"
   docker compose exec backend alembic upgrade head
   ```

### Archivos a tocar
- `backend/app/publication/models.py` — agregar PublicationSession
- `backend/app/publication/service.py` — implementar process_message()

---

## PRIORIDAD 2 — Grupo B: Seedear categorias

**Problema**: la tabla `categories` esta vacia. El feed con filtros y el flujo del bot necesitan categorias.

### Tareas

1. Insertar categorias base en la DB. Opciones:
   - **Opcion A** — Script SQL en `database/seed.sql`:
     ```sql
     INSERT INTO categories (id, name, slug) VALUES
       (gen_random_uuid(), 'Venta', 'venta'),
       (gen_random_uuid(), 'Servicio', 'servicio'),
       (gen_random_uuid(), 'Evento', 'evento'),
       (gen_random_uuid(), 'Otro', 'otro')
     ON CONFLICT (slug) DO NOTHING;
     ```
   - **Opcion B** — Endpoint o script Python que lo haga al arrancar

2. Mapear la respuesta del usuario (1, 2, 3, 4) al `category_id` correspondiente en `process_message()`

---

## PRIORIDAD 3 — Compartido: Manejo de imagenes

**Problema**: el webhook ignora mensajes que no son texto. Para el paso "envia una foto" del flujo de publicacion se necesita recibir imagenes.

### Tareas

1. **Extender el webhook** en `backend/app/webhook/router.py`
   - En `_extract_phone_and_text()`, agregar soporte para `msg_type == "image"`
   - Extraer la URL de la imagen del payload de Kapso
   - Retornar la URL junto con phone para que el service la procese

2. **Subir imagen a Cloudinary** (requiere las 3 keys en `.env`)
   - Crear helper en `backend/app/shared/cloudinary.py`
   - Descargar la imagen desde la URL de Kapso y subirla a Cloudinary
   - Devolver la URL publica de Cloudinary

3. **Asociar imagen a publicacion**
   - En `PublicationService`, cuando el paso actual es "media" y el usuario envia imagen:
     - Subir a Cloudinary
     - Crear registro en tabla `media` asociado a la publicacion

### Archivos a tocar
- `backend/app/webhook/router.py` — soporte para tipo image
- `backend/app/shared/cloudinary.py` — nuevo, helper de upload
- `backend/app/publication/service.py` — manejar paso de media

### Variables de entorno necesarias
```
CLOUDINARY_CLOUD_NAME=tu-cloud-name
CLOUDINARY_API_KEY=tu-api-key
CLOUDINARY_API_SECRET=tu-api-secret
```

---

## PRIORIDAD 4 — Grupo A: Polish y endpoint faltante

### Tareas

1. **Agregar `POST /api/v1/onboarding/start`** en `backend/app/onboarding/router.py`
   - Segun el contrato de API en STEPS.md, este endpoint deberia existir
   - Funcion: iniciar onboarding manualmente (util para testing)

2. **Mejorar frontend admin**
   - Agregar filtros por estado de onboarding en UserList
   - Agregar busqueda por telefono o nombre
   - Mejorar UI/styling del dashboard y las cards

3. **Limpiar componente no usado**
   - `OnboardingStats.tsx` no esta conectado — usarlo en AdminDashboard o eliminarlo

---

## PRIORIDAD 5 — Grupo B: Polish frontend

### Tareas

1. **Conectar `CategoryFilter`** en `frontend/src/publication/pages/Feed.tsx`
   - Fetch categorias desde `GET /api/v1/publications/categories`
   - Pasar categoria seleccionada como query param al listar publicaciones

2. **Usar `MediaGallery`** en `frontend/src/publication/pages/PublicationDetail.tsx`
   - Actualmente la logica de renderizar imagenes esta inline y duplicada
   - Reemplazar con el componente `MediaGallery` que ya existe

3. **Mejorar ModerationPanel**
   - Agregar input para razon de rechazo (ahora hardcodea "Rechazado por moderador")
   - Mostrar mas detalle de la publicacion en la vista de moderacion

---

## Orden de ejecucion recomendado

```
Grupo A                              Grupo B
────────                             ────────
                                     1. PublicationSession model + migracion
                                     2. Implementar process_message() completo
                                     3. Seedear categorias
1. POST /onboarding/start            4. Testear flujo de publicacion por bot
2. Mejorar frontend admin            5. Conectar CategoryFilter en Feed
                                     
         ── SYNC: probar flujo completo end-to-end ──
         
3. Ayudar con imagenes               6. Manejo de imagenes (Cloudinary)
4. Polish final                      7. Polish frontend publicacion

         ── SYNC: integracion final + demo ──
```

---

## Como testear el flujo completo

Una vez implementado todo:

1. Enviar mensaje al bot desde WhatsApp (numero sandbox de Kapso)
2. Completar onboarding (4 pasos: nombre, email, ciudad, bio)
3. Escribir "publicar" → completar los 5 pasos de publicacion
4. Verificar en `http://localhost:5173/moderation` que la publicacion aparece como pendiente
5. Aprobar desde el panel → verificar que aparece en `http://localhost:5173/` (feed)
6. Verificar en `http://localhost:5173/admin` que el usuario aparece como onboarded
