from __future__ import annotations

"""
Ejemplos ancla editables para la linea base clasica de NeuroGuia.

La idea es mantener separados:
- ejemplos de categorias funcionales
- ejemplos de intenciones conversacionales

Estos anchors sirven como dataset minimo inicial. Cuando exista un
corpus etiquetado mas grande, se puede sustituir o complementar sin
tener que reescribir la logica del clasificador.
"""


CATEGORY_ANCHOR_EXAMPLES = {
    "crisis_activa": [
        "ahorita esta en crisis y no lo puedo calmar",
        "esta gritando y golpeando cosas en este momento",
        "se salio de control y hay riesgo de que lastime a alguien",
        "me esta pegando y no se como detener esto",
    ],
    "escalada_emocional": [
        "ya se esta empezando a alterar y sube el tono",
        "antes de explotar se pone muy tenso e irritable",
        "veo que va escalando y se esta frustrando mas",
        "todavia no es crisis pero ya viene subiendo",
    ],
    "prevencion_escalada": [
        "como evito que vuelva a pasar esto",
        "quiero prevenir otra crisis antes de que escale",
        "que senales tempranas debo mirar para anticiparlo",
        "que hago antes para que no llegue al pico",
    ],
    "ansiedad_cognitiva": [
        "me abruma pensar en todos los pendientes",
        "no dejo de pensar y me da mucha ansiedad",
        "tengo la cabeza llena y me saturo mentalmente",
        "me angustia todo lo que tengo que hacer",
    ],
    "disfuncion_ejecutiva": [
        "no puedo empezar y me bloqueo con la tarea",
        "veo todo lo que tengo que hacer y no arranco",
        "procrastino porque no se por donde empezar",
        "no logro dar el primer paso aunque quiero hacerlo",
    ],
    "sobrecarga_sensorial": [
        "hay demasiado ruido y se satura muy rapido",
        "las luces y la gente lo sobreestimulan",
        "no tolera los sonidos ni el ambiente cargado",
        "se abruma con muchas personas y mucho estimulo",
    ],
    "regulacion_post_evento": [
        "que hago despues de la crisis cuando ya se calma",
        "como hablarlo despues de que baje la intensidad",
        "ya paso todo, ahora como lo acompano",
        "despues del desborde no se que hacer para reparar",
    ],
    "sobrecarga_cuidador": [
        "yo tambien estoy agotada y ya no puedo con esto",
        "me siento rebasada y sola con toda la carga",
        "todo recae en mi y estoy muy cansado",
        "esto me supera y siento que me estoy rompiendo",
    ],
    "sueno_regulacion": [
        "no logra dormir y tarda mucho en conciliar el sueno",
        "duerme mal y se despierta muchas veces",
        "se desvela y la noche siempre termina muy pesada",
        "necesitamos una rutina suave para ir a dormir",
    ],
    "transicion_rigidez": [
        "cuando cambia el plan se desregula mucho",
        "le cuesta mucho pasar de una actividad a otra",
        "las transiciones y cambios inesperados lo desorganizan",
        "necesita mucha anticipacion cuando algo va a cambiar",
    ],
    "apoyo_general": [
        "necesito orientacion porque no se que hacer",
        "quiero apoyo para entender mejor lo que pasa",
        "me preocupa esta situacion y necesito ayuda",
        "solo necesito una guia clara para empezar",
    ],
}


INTENT_ANCHOR_EXAMPLES = {
    "urgent_support": [
        "necesito ayuda urgente porque esta en crisis",
        "me urge saber que hacer ahora mismo",
        "hay riesgo y no logro contener la situacion",
        "ya no puedo controlarlo y necesito ayuda inmediata",
    ],
    "prevention_request": [
        "como puedo prevenir que esto vuelva a pasar",
        "quiero evitar otra crisis antes de que escale",
        "que hago para anticiparme la proxima vez",
        "como detectar las senales tempranas",
    ],
    "strategy_feedback": [
        "eso ya lo intente y no funciono",
        "ya hicimos esa estrategia y no ayudo",
        "lo que probamos sirvio poco y luego empeoro",
        "necesito otra opcion porque eso no resulto",
    ],
    "anxiety_relief_request": [
        "me da ansiedad pensar en todo lo pendiente",
        "necesito ayuda para bajar mi ansiedad",
        "me abruma todo y no dejo de pensar",
        "quiero calmar esta saturacion mental",
    ],
    "executive_support_request": [
        "ayudame a empezar porque estoy bloqueado",
        "necesito un primer paso claro para arrancar",
        "no puedo organizarme y quiero avanzar",
        "dame apoyo para salir del bloqueo con la tarea",
    ],
    "routine_request": [
        "dame una rutina concreta para esto",
        "quiero pasos claros y una secuencia simple",
        "necesito una estrategia concreta para seguir",
        "puedes darme un plan breve paso a paso",
    ],
    "clarification_request": [
        "explicame mejor a que te refieres",
        "no entendi, puedes aclararmelo",
        "que significa eso exactamente",
        "como funciona lo que me propones",
    ],
    "followup": [
        "si, seguimos",
        "ok, continuamos",
        "te actualizo con lo que paso despues",
        "retomemos lo que estabamos viendo",
    ],
    "profile_question": [
        "por que le pasa esto y como entenderlo mejor",
        "esto es normal o que podria estar pasando",
        "como entender mejor este perfil",
        "quiero comprender que hay detras de esta reaccion",
    ],
    "emotional_venting": [
        "solo queria decir que me siento muy frustrada",
        "me siento culpable y agotada",
        "estoy desesperado y necesitaba expresarlo",
        "me rebasa todo esto y queria decirlo",
    ],
    "general_support": [
        "necesito ayuda con esta situacion",
        "quiero apoyo para saber por donde empezar",
        "me preocupa esto y no se como manejarlo",
        "busco orientacion general para avanzar",
    ],
}
