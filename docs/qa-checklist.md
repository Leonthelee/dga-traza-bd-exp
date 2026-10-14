# Validación del piloto QA

Registrar fecha, instancia, versión, operador, captura y resultado de cada punto. Ningún punto se considera aprobado por la existencia de este archivo.

- [ ] Confirmar QA y `@@SERVERNAME`, BD de CPA, BD_EXP, BD_MAP y login real del legacy.
- [ ] Probar preflight con usuario dedicado y permisos mínimos; probar rechazo de servidor incorrecto.
- [ ] Verificar componentes XE y unidades de duration/cpu_time en esa versión.
- [ ] Verificar escritura XEL por la cuenta del servicio SQL; probar ruta sin permiso.
- [ ] Usar una carga conocida con SP padre, SP hijo, recursión y SQL dinámico. Comparar nombres, orden y métricas con SSMS.
- [ ] Ejecutar dos solicitudes seguidas por la misma conexión: árboles separados.
- [ ] Ejecutar solicitudes concurrentes/MARS si el cliente lo usa: no aceptar enlaces ambiguos como ciertos.
- [ ] Probar Agregar Opositor una sola vez: contrastar los diez módulos del PDF, no asumir que siempre se ejecutan en toda condición.
- [ ] Probar saltos hacia BD_MAP y la base de CPA sin filtrar por nombre de base.
- [ ] Cerrar solo el navegador: captura y parada por plazo deben continuar.
- [ ] Solicitar parada durante importación: SQL debe quedar detenido aunque la importación sea parcial.
- [ ] Simular fallo del recolector y recuperar desde SSMS/CLI; comprobar que no queda sesión activa.
- [ ] Reimportar dos veces y verificar conteo estable.
- [ ] Medir una carga con y sin captura: CPU, latencia, I/O y bytes XEL. Acordar umbral de overhead aceptable antes de ampliar duración.
- [ ] Revisar pérdida de eventos/buffers y rollover. Un cero en contadores NO prueba integridad del archivo.
- [ ] Revisar Excel/CSV y protección de datos antes de compartir.
- [ ] Detener y retirar las definiciones XE del piloto. Registrar qué evidencia se conserva y por cuánto tiempo.

## Puerta a producción (trabajo futuro)

No habilitada por este piloto. Requiere resultados QA, parada garantizada desde servidor (p. ej. job SQL Agent administrado por DBA), retención dimensionada, supervisión del recolector, autenticación si se comparte interfaz, revisión de permisos y carga. Cambiar `environment` a PROD está bloqueado en código.
