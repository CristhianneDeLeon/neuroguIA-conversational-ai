-- neuroguIA
-- Corrección del valor predeterminado de created_at
-- Tabla: public.ng_messages
-- Fecha: 2026-08-01
--
-- Evita errores NotNullViolation cuando la aplicación
-- guarda mensajes sin enviar created_at explícitamente.

begin;

alter table public.ng_messages
    alter column created_at set default now();

commit;
