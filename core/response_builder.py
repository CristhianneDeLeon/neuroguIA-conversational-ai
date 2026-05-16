from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class ResponseBuilder:
    """
    Final response assembler.

    Normal path:
    - pass through approved LLM text with minimal cleanup

    Fallback path:
    - render a local response from response_goal + conversation state
    - keep domain specificity visible
    - avoid a universal opening/body/closing skeleton
    """

    INTERNAL_TEXT_PATTERNS = [
        r"\bapoyo_general\b",
        r"\bgeneral_support\b",
        r"\bdisfuncion_ejecutiva\b",
        r"\bansiedad_cognitiva\b",
        r"\bprevencion_escalada\b",
        r"\bregulacion_post_evento\b",
        r"\bsobrecarga_sensorial\b",
        r"\btransicion_rigidez\b",
        r"\bsueno_regulacion\b",
        r"\bcrisis_activa\b",
        r"\breception_containment\b",
        r"\badaptive_intervention\b",
        r"\bfocus_clarification\b",
    ]

    ROBOTIC_OPENING_PATTERNS = [
        r"^\s*la respuesta mas util aqui es[:\s,]*",
        r"^\s*la respuesta mas util es[:\s,]*",
        r"^\s*lo mas util suele ser[:\s,]*",
        r"^\s*lo mas util aqui es[:\s,]*",
        r"^\s*en este caso[:\s,]*",
    ]

    def build(
        self,
        decision_payload: Optional[Dict[str, Any]] = None,
        state_analysis: Optional[Dict[str, Any]] = None,
        stage_result: Optional[Dict[str, Any]] = None,
        routine_payload: Optional[Dict[str, Any]] = None,
        response_memory_payload: Optional[Dict[str, Any]] = None,
        fallback_payload: Optional[Dict[str, Any]] = None,
        llm_curated_payload: Optional[Dict[str, Any]] = None,
        category_analysis: Optional[Dict[str, Any]] = None,
        intent_analysis: Optional[Dict[str, Any]] = None,
        conversation_frame: Optional[Dict[str, Any]] = None,
        expert_adaptation_plan: Optional[Dict[str, Any]] = None,
        conversational_intent: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        decision_payload = decision_payload or {}
        state_analysis = state_analysis or {}
        stage_result = stage_result or {}
        routine_payload = routine_payload or {}
        response_memory_payload = response_memory_payload or {}
        fallback_payload = fallback_payload or {}
        llm_curated_payload = llm_curated_payload or {}
        category_analysis = category_analysis or {}
        intent_analysis = intent_analysis or {}
        conversation_frame = conversation_frame or {}
        conversational_intent = conversational_intent or {}

        response_goal = decision_payload.get("response_goal", {}) or {}
        selected_strategy = decision_payload.get("selected_strategy")
        selected_microaction = decision_payload.get("selected_microaction")
        decision_mode = decision_payload.get("decision_mode", "planned_response")
        domain = conversation_frame.get("conversation_domain") or category_analysis.get("detected_category") or "apoyo_general"
        phase = conversation_frame.get("conversation_phase") or stage_result.get("conversation_phase") or "clarification"

        if fallback_payload.get("use_llm") and llm_curated_payload.get("approved"):
            curated_text = str(llm_curated_payload.get("curated_response_text") or "").strip()
            final_text = self._clean_text(curated_text)
            curated_mode = "stub_curated" if llm_curated_payload.get("used_stub_fallback") else "llm_curated"
            return self._package(
                text=final_text,
                mode=curated_mode,
                decision_mode=decision_mode,
                domain=domain,
                phase=phase,
                category_analysis=category_analysis,
                intent_analysis=intent_analysis,
                selected_strategy=selected_strategy,
                selected_microaction=selected_microaction,
                suggested_question=self._first_question(response_goal),
            )

        if decision_mode == "reuse_response_memory":
            reuse_candidate = decision_payload.get("reuse_response_candidate") or response_memory_payload.get("best_response") or {}
            reused_text = self._clean_text(str(reuse_candidate.get("response_text") or "").strip())
            if reused_text:
                return self._package(
                    text=reused_text,
                    mode="reuse_response_memory",
                    decision_mode=decision_mode,
                    domain=domain,
                    phase=phase,
                    category_analysis=category_analysis,
                    intent_analysis=intent_analysis,
                    selected_strategy=selected_strategy,
                    selected_microaction=selected_microaction,
                    suggested_question=self._first_question(response_goal),
                )

        fallback_text = self._render_fallback(
            response_goal=response_goal,
            conversational_intent=conversational_intent,
            conversation_frame=conversation_frame,
            state_analysis=state_analysis,
            category_analysis=category_analysis,
        )
        return self._package(
            text=fallback_text,
            mode="system_generated",
            decision_mode=decision_mode,
            domain=domain,
            phase=phase,
            category_analysis=category_analysis,
            intent_analysis=intent_analysis,
            selected_strategy=selected_strategy,
            selected_microaction=selected_microaction,
            suggested_question=self._first_question(response_goal),
        )

    def _render_fallback(
        self,
        response_goal: Dict[str, Any],
        conversational_intent: Dict[str, Any],
        conversation_frame: Dict[str, Any],
        state_analysis: Dict[str, Any],
        category_analysis: Dict[str, Any],
    ) -> str:
        domain = conversation_frame.get("conversation_domain") or category_analysis.get("detected_category") or "apoyo_general"
        turn_family = conversation_frame.get("turn_family") or "new_request"
        response_shape = self._response_shape(response_goal)
        form_variant = self._form_variant(response_goal)
        actions = [str(item).strip() for item in response_goal.get("candidate_actions", []) if str(item).strip()]
        questions = [str(item).strip() for item in response_goal.get("possible_questions", []) if str(item).strip()]
        contents = [str(item).strip() for item in response_goal.get("suggested_content", []) if str(item).strip()]
        literal_phrases = [str(item).strip() for item in response_goal.get("literal_phrase_candidates", []) if str(item).strip()]
        rhythm = str(conversational_intent.get("rhythm") or "steady")
        pressure = str(conversational_intent.get("pressure") or "low")
        permissiveness = str(conversational_intent.get("permissiveness") or "moderate")
        closing_style = str(conversational_intent.get("closing_style") or "none")

        primary_text = self._render_shape_text(
            domain=domain,
            turn_family=turn_family,
            response_shape=response_shape,
            form_variant=form_variant,
            actions=actions,
            questions=questions,
            contents=contents,
            literal_phrases=literal_phrases,
            rhythm=rhythm,
            pressure=pressure,
            permissiveness=permissiveness,
        )
        closing_text = self._render_optional_close(
            domain=domain,
            response_goal=response_goal,
            questions=questions,
            response_shape=response_shape,
            closing_style=closing_style,
            permissiveness=permissiveness,
        )
        return self._clean_text(self._join_parts(primary_text, closing_text))

    def _render_shape_text(
        self,
        domain: str,
        turn_family: str,
        response_shape: str,
        form_variant: str,
        actions: List[str],
        questions: List[str],
        contents: List[str],
        literal_phrases: List[str],
        rhythm: str,
        pressure: str,
        permissiveness: str,
    ) -> str:
        action = actions[0] if actions else None
        content = contents[0] if contents else None
        literal_phrase = literal_phrases[0] if literal_phrases else None

        if response_shape == "meta_answer":
            return self._sentence(content or "Soy NeuroGuIA.")
        if response_shape == "simple_answer":
            return self._sentence(content or self._domain_simple_answer(domain))
        if response_shape == "validation_answer":
            return self._sentence(content or self._domain_validation_answer(domain))
        if response_shape == "clarify_simple":
            return self._render_clarify_simple(domain=domain, action=action, content=content)
        if response_shape == "literal_phrase":
            return self._render_literal_phrase(domain=domain, phrase=literal_phrase or action)
        if response_shape == "strategy_switch":
            return self._render_strategy_switch(domain=domain, action=action, form_variant=form_variant)
        if response_shape == "guided_steps":
            return self._render_guided_steps(domain=domain, actions=actions, literal_phrase=literal_phrase)
        if response_shape == "check_effect":
            return self._render_check_effect(domain=domain, action=action)
        if response_shape == "hold_line":
            return self._render_hold_line(domain=domain, action=action, form_variant=form_variant)
        if response_shape == "closure_pause":
            return self._render_closure_pause(domain=domain, form_variant=form_variant)
        if response_shape == "direct_instruction":
            return self._render_direct_instruction(domain=domain, actions=actions)
        if response_shape == "guided_decision":
            return self._render_guided_decision(domain=domain, action=action, form_variant=form_variant)
        if response_shape in {"single_action", "concrete_action"}:
            return self._render_single_action(
                domain=domain,
                turn_family=turn_family,
                action=action,
                form_variant=form_variant,
                pressure=pressure,
            )
        if response_shape == "crisis_containment":
            return self._render_crisis_containment(action=action, content=content)
        if response_shape == "grounding":
            return self._render_grounding(action=action, content=content, rhythm=rhythm, permissiveness=permissiveness)
        if response_shape == "permission_phrase":
            return self._render_permission_phrase(action=action)
        if response_shape == "load_relief":
            return self._render_load_relief(action=action, content=content)
        if response_shape == "sleep_settle":
            return self._render_sleep_settle(action=action, content=content)
        if response_shape == "sleep_scan":
            return self._render_sleep_scan(action=action)
        if response_shape == "permission_pause":
            return self._render_permission_pause(action=action, content=content, domain=domain)

        if action:
            return self._render_single_action(
                domain=domain,
                turn_family=turn_family,
                action=action,
                form_variant=form_variant,
                pressure=pressure,
            )
        if content:
            return self._sentence(content)
        if questions:
            return self._sentence(questions[0])
        return self._sentence(self._domain_support_line(domain))

    def _render_clarify_simple(self, domain: str, action: Optional[str], content: Optional[str]) -> str:
        if content:
            return self._sentence(content)
        if domain == "disfuncion_ejecutiva":
            return self._sentence(action or "Solo busco dejarte un comienzo visible, no ordenar todo")
        if domain == "ansiedad_cognitiva":
            return self._sentence(action or "Solo quiero bajar un poco el ruido y dejar una cosa clara")
        if domain == "crisis_activa":
            return self._sentence(action or "Primero toca bajar ruido y dar espacio")
        return self._sentence(action or "Solo queria dejar una idea mas simple")

    def _render_literal_phrase(self, domain: str, phrase: Optional[str]) -> str:
        phrase = (phrase or self._default_literal_phrase(domain)).strip()
        return self._join_parts(
            f'Puedes decirle esto, tal cual: "{phrase}"',
            self._sentence(self._literal_followup_line(domain)),
        )

    def _render_strategy_switch(self, domain: str, action: Optional[str], form_variant: str) -> str:
        switch_action = action or self._default_action_for_domain(domain)
        if form_variant == "outcome_worse":
            return self._sentence(f"Por ahi no. Prueba mejor con esto: {switch_action}")
        if form_variant == "outcome_no_change":
            return self._sentence(f"Eso no movio nada. Vamos por otro lado: {switch_action}")
        if domain == "crisis_activa":
            return self._sentence(f"No repitas lo anterior. Haz este cambio: {switch_action}")
        if domain == "disfuncion_ejecutiva":
            return self._sentence(f"Ese arranque no ayudo. Cambia a esto: {switch_action}")
        return self._sentence(f"Probemos distinto: {switch_action}")

    def _render_guided_steps(self, domain: str, actions: List[str], literal_phrase: Optional[str]) -> str:
        steps = list(actions[:2])
        if literal_phrase:
            steps.append(f'Di solo esto: "{literal_phrase}"')
        if not steps:
            steps = self._default_steps_for_domain(domain)
        return self._render_steps("", steps[:3])

    def _render_check_effect(self, domain: str, action: Optional[str]) -> str:
        check_action = action or self._default_check_for_domain(domain)
        if domain == "crisis_activa":
            return self._sentence("Solo mira si bajo un poco la tension. Si bajo, no metas nada mas todavia")
        if domain == "disfuncion_ejecutiva":
            return self._sentence(f"Antes de sumar otra cosa, mira esto: {check_action}")
        return self._sentence(f"Mira solo esto: {check_action}")

    def _render_hold_line(self, domain: str, action: Optional[str], form_variant: str) -> str:
        hold_action = action or self._default_hold_line(domain)
        if form_variant == "partial_relief_hold":
            return self._sentence(f"Si ya aflojo un poco, basta con {hold_action}")
        if form_variant == "outcome_worse":
            return self._sentence(f"No lo empujes mas por ahi. {hold_action}")
        return self._sentence(hold_action)

    def _render_closure_pause(self, domain: str, form_variant: str) -> str:
        if domain == "crisis_activa":
            return self._sentence("Si ya bajo un poco, aqui podemos parar. No hace falta meter nada mas ahora")
        if domain == "ansiedad_cognitiva":
            return self._sentence("Con eso basta por ahora. No hace falta seguir apretando este tema")
        if domain == "disfuncion_ejecutiva":
            return self._sentence("Con eso alcanza por ahora. No hace falta abrir otro paso")
        if form_variant == "close_after_action":
            return self._sentence("Por ahora basta. Puedes dejarlo aqui")
        return self._sentence("Aqui podemos parar por ahora")

    def _render_direct_instruction(self, domain: str, actions: List[str]) -> str:
        steps = actions[:3] or self._default_steps_for_domain(domain)
        if domain == "crisis_activa":
            return self._render_steps("", steps)
        if len(steps) == 1:
            return self._sentence(steps[0])
        return self._render_steps("", steps)

    def _render_guided_decision(self, domain: str, action: Optional[str], form_variant: str) -> str:
        chosen = action or self._default_action_for_domain(domain)
        if domain == "ansiedad_cognitiva":
            return self._sentence(f"Voy a elegir por ti una sola cosa: {chosen}. Lo demas se queda quieto por ahora")
        if domain == "disfuncion_ejecutiva":
            return self._sentence(f"Voy a cerrarte la decision: {chosen}")
        if form_variant == "stop_or_continue":
            return self._sentence(chosen)
        return self._sentence(f"Dejalo asi por ahora: {chosen}")

    def _render_single_action(
        self,
        domain: str,
        turn_family: str,
        action: Optional[str],
        form_variant: str,
        pressure: str,
    ) -> str:
        action = action or self._default_action_for_domain(domain)
        if domain == "crisis_activa":
            return self._sentence(f"Empieza por {action}")
        if domain == "ansiedad_cognitiva":
            if turn_family == "specific_action_request":
                return self._sentence(action)
            if form_variant == "action_pivot":
                return self._sentence(f"Llevalo a algo visible: {action}")
            return self._sentence(f"Ve solo con esto: {action}")
        if domain == "disfuncion_ejecutiva":
            if form_variant == "visible_start":
                return self._sentence(f"Empieza aqui: {action}")
            return self._sentence(action if pressure == "medium" else f"Ve directo a esto: {action}")
        if domain == "sueno_regulacion":
            return self._sentence(f"Empieza por {action}")
        if domain == "sobrecarga_cuidador":
            return self._sentence(f"Hoy basta con {action}")
        if domain == "sobrecarga_sensorial":
            return self._sentence(f"Baja primero esto: {action}")
        if domain == "transicion_rigidez":
            return self._sentence(f"Haz predecible el cambio con esto: {action}")
        if domain == "prevencion_escalada":
            return self._sentence(f"Deja lista solo esta referencia: {action}")
        if domain == "regulacion_post_evento":
            return self._sentence(f"Quedate con esto: {action}")
        return self._sentence(f"Quedate solo con esto por ahora: {action}")

    def _render_crisis_containment(self, action: Optional[str], content: Optional[str]) -> str:
        if action:
            return self._join_parts(
                self._sentence("Estoy contigo. Lo primero es bajar demanda alrededor"),
                self._sentence(action),
            )
        if content:
            return self._sentence(content)
        return self._sentence("Estoy contigo. Lo primero es bajar demanda y ruido alrededor")

    def _render_grounding(
        self,
        action: Optional[str],
        content: Optional[str],
        rhythm: str,
        permissiveness: str,
    ) -> str:
        lead = content or ("No hace falta resolverlo mas ahora" if permissiveness == "high" else "Vamos a bajar un poco la activacion")
        grounding_action = action or "apoya los pies en el piso y suelta el aire mas largo una vez"
        if rhythm == "direct":
            return self._join_parts(self._sentence(lead), self._sentence(f"{grounding_action}. Nada mas por ahora"))
        return self._join_parts(self._sentence(lead), self._sentence(grounding_action))

    def _render_permission_phrase(self, action: Optional[str]) -> str:
        phrase = (action or "solo voy con una cosa por vez").strip()
        if not phrase.startswith('"'):
            phrase = f'"{phrase}"'
        return self._sentence(f"Si te sirve, repite solo esto: {phrase}")

    def _render_load_relief(self, action: Optional[str], content: Optional[str]) -> str:
        lead = self._sentence(content or "Hoy no hace falta poder con todo")
        relief_action = self._sentence(action or "deja una sola cosa para despues sin resolverla hoy")
        return self._join_parts(lead, relief_action)

    def _render_sleep_settle(self, action: Optional[str], content: Optional[str]) -> str:
        lead = self._sentence(content or "No intentes resolver toda la noche ahora")
        settle_action = self._sentence(action or "baja una sola fuente de luz, ruido o pantalla antes de acostarte")
        return self._join_parts(lead, settle_action)

    def _render_sleep_scan(self, action: Optional[str]) -> str:
        return self._sentence(action or "Mira solo que esta activando mas ahora: mente, ruido o cuerpo")

    def _render_permission_pause(self, action: Optional[str], content: Optional[str], domain: str) -> str:
        if content:
            base = self._sentence(content)
        elif domain == "ansiedad_cognitiva":
            base = self._sentence("No hace falta resolverlo todo ahora")
        elif domain == "sobrecarga_cuidador":
            base = self._sentence("Hoy no tienes que aclararlo todo")
        else:
            base = self._sentence("Esta bien no tenerlo claro todavia")
        if action:
            return self._join_parts(base, self._sentence(f"Por ahora basta con {action}"))
        return base

    def _render_optional_close(
        self,
        domain: str,
        response_goal: Dict[str, Any],
        questions: List[str],
        response_shape: str,
        closing_style: str,
        permissiveness: str,
    ) -> Optional[str]:
        if closing_style == "brief_check" and response_goal.get("should_offer_question") and questions:
            return self._sentence(questions[0])
        if closing_style != "soft_stop":
            return None
        if response_shape in {"closure_pause", "permission_pause", "hold_line", "load_relief", "sleep_settle"}:
            return None
        if domain == "ansiedad_cognitiva":
            return self._sentence("Si ahora no sale mas, con eso basta")
        if domain == "disfuncion_ejecutiva":
            return self._sentence("Con eso alcanza por ahora")
        if domain == "sobrecarga_cuidador":
            return self._sentence("Puedes dejarlo ahi por hoy")
        if permissiveness == "high":
            return self._sentence("Puedes parar aqui por ahora")
        return None

    def _default_literal_phrase(self, domain: str) -> str:
        mapping = {
            "crisis_activa": "Estoy aqui contigo. No voy a discutir ahora. Vamos a bajar un poco esto.",
            "ansiedad_cognitiva": "No voy a resolver todo ahora. Solo una cosa por vez.",
            "disfuncion_ejecutiva": "No voy a ordenar todo. Solo voy a empezar por una parte pequena.",
            "transicion_rigidez": "Ahora termina esto. Luego va lo siguiente.",
        }
        return mapping.get(domain, "Vamos con una sola cosa por ahora.")

    def _literal_followup_line(self, domain: str) -> str:
        if domain == "crisis_activa":
            return "Despues calla un momento y deja espacio"
        if domain == "ansiedad_cognitiva":
            return "La idea es bajar ruido, no explicarlo todo"
        return "Despues deja unos segundos antes de agregar otra cosa"

    def _default_steps_for_domain(self, domain: str) -> List[str]:
        mapping = {
            "crisis_activa": [
                "quita una fuente de ruido, exigencia o gente alrededor",
                "ponte de lado y usa pocas palabras",
                "espera unos segundos antes de volver a hablar",
            ],
            "disfuncion_ejecutiva": [
                "abre el material que toca",
                "escribe el titulo o primer punto",
                "deja el cursor listo en la siguiente linea",
            ],
            "ansiedad_cognitiva": [
                "cierra lo demas que tengas abierto",
                "escribe una sola frase con lo que mas te aprieta",
                "para ahi",
            ],
        }
        return mapping.get(domain, [self._default_action_for_domain(domain)])

    def _default_action_for_domain(self, domain: str) -> str:
        mapping = {
            "crisis_activa": "quitar una sola fuente de ruido, exigencia o gente alrededor",
            "ansiedad_cognitiva": "apoya los pies en el piso y suelta el aire mas largo una vez",
            "disfuncion_ejecutiva": "abre solo el material que toca",
            "sueno_regulacion": "baja una sola fuente de luz, ruido o pantalla",
            "sobrecarga_cuidador": "deja una sola cosa para despues",
            "sobrecarga_sensorial": "baja un estimulo concreto",
            "transicion_rigidez": "di en una frase que sigue ahora",
            "prevencion_escalada": "ubica la primera senal de subida",
            "regulacion_post_evento": "rescata una sola senal util",
        }
        return mapping.get(domain, "quedate con una sola cosa clara por ahora")

    def _default_check_for_domain(self, domain: str) -> str:
        mapping = {
            "ansiedad_cognitiva": "si bajo un poco el ruido mental",
            "disfuncion_ejecutiva": "si ya quedo un arranque visible",
            "sueno_regulacion": "si bajo un poco la activacion",
        }
        return mapping.get(domain, "si eso ya ayudo un poco")

    def _default_hold_line(self, domain: str) -> str:
        mapping = {
            "crisis_activa": "Manten solo lo anterior y no agregues otra indicacion",
            "ansiedad_cognitiva": "Quedate con eso y no abras otra cosa ahora",
            "disfuncion_ejecutiva": "Sosten ese arranque sin meter otra decision",
        }
        return mapping.get(domain, "Manten lo anterior sin sumar nada mas")

    def _domain_simple_answer(self, domain: str) -> str:
        mapping = {
            "crisis_activa": "Si sigue habiendo mucha activacion, importa mas bajar demanda que hablar mucho",
            "ansiedad_cognitiva": "Si la mente va muy rapido, primero ayuda bajar ruido y despues decidir",
            "disfuncion_ejecutiva": "Cuando hay bloqueo, suele ayudar mas dejar algo visible que organizar todo",
            "sueno_regulacion": "Cuando el cuerpo esta cansado pero la activacion sigue alta, conviene bajar activacion antes de forzar el sueno",
        }
        return mapping.get(domain, self._domain_support_line(domain))

    def _domain_validation_answer(self, domain: str) -> str:
        mapping = {
            "crisis_activa": "Si, en una crisis es esperable que no sirva razonar mucho de entrada",
            "ansiedad_cognitiva": "Si, con ansiedad alta puede costar mucho pensar con claridad o decidir",
            "disfuncion_ejecutiva": "Si, en bloqueo ejecutivo es comun quedarse frenado incluso queriendo empezar",
            "sueno_regulacion": "Si, con cansancio acumulado o activacion alta dormir bien se vuelve mucho mas dificil",
            "sobrecarga_cuidador": "Si, cuando vienes cargando mucho es esperable sentirte sin margen",
        }
        return mapping.get(domain, "Si, eso puede pasar cuando hay mucha carga")

    def _domain_support_line(self, domain: str) -> str:
        mapping = {
            "crisis_activa": "Lo primero aqui es sostener seguridad y bajar demanda",
            "ansiedad_cognitiva": "Lo primero aqui es bajar activacion y ruido mental",
            "disfuncion_ejecutiva": "Lo primero aqui es bajar friccion y dejar un arranque visible",
            "sueno_regulacion": "Lo primero aqui es bajar activacion y cuidar el descanso",
            "sobrecarga_cuidador": "Lo primero aqui es aliviar carga antes de pedir mas",
            "sobrecarga_sensorial": "Lo primero aqui es bajar un estimulo concreto",
            "transicion_rigidez": "Lo primero aqui es volver el cambio mas predecible",
            "prevencion_escalada": "Lo primero aqui es ubicar la senal temprana y responder antes",
            "regulacion_post_evento": "Lo primero aqui es reparar sin reabrir todo",
        }
        return mapping.get(domain, "Vamos con una sola cosa clara por ahora")

    def _package(
        self,
        text: str,
        mode: str,
        decision_mode: str,
        domain: str,
        phase: str,
        category_analysis: Dict[str, Any],
        intent_analysis: Dict[str, Any],
        selected_strategy: Optional[str],
        selected_microaction: Optional[str],
        suggested_question: Optional[str],
    ) -> Dict[str, Any]:
        final_text = self._clean_text(text)
        return {
            "response": final_text,
            "text": final_text,
            "mode": mode,
            "opening": None,
            "focus_line": None,
            "body": final_text,
            "closing": None,
            "suggested_question": suggested_question,
            "suggested_strategy": selected_strategy,
            "suggested_microaction": selected_microaction,
            "response_metadata": {
                "decision_mode": decision_mode,
                "output_source": mode,
                "detected_category": category_analysis.get("detected_category"),
                "detected_intent": intent_analysis.get("detected_intent"),
                "conversation_domain": domain,
                "conversation_phase": phase,
            },
        }

    def _render_steps(self, intro: str, steps: List[str]) -> str:
        lines = [intro, ""] if intro else []
        for index, step in enumerate([step for step in steps if step], start=1):
            lines.append(f"{index}. {self._strip_terminal_punctuation(step)}")
        return "\n".join(lines)

    def _first_question(self, response_goal: Dict[str, Any]) -> Optional[str]:
        if not response_goal.get("should_offer_question"):
            return None
        if str(response_goal.get("followup_policy") or "avoid") == "avoid":
            return None
        questions = [str(item).strip() for item in response_goal.get("possible_questions", []) if str(item).strip()]
        return questions[0] if questions else None

    def _join_parts(self, *parts: Optional[str]) -> str:
        return "\n\n".join([str(part).strip() for part in parts if str(part or "").strip()])

    def _sentence(self, text: Optional[str]) -> str:
        text = str(text or "").strip()
        if not text:
            return ""
        if text[-1] not in ".!?":
            text += "."
        return text[0].upper() + text[1:]

    def _strip_terminal_punctuation(self, text: str) -> str:
        return str(text or "").strip().rstrip(".!?")

    def _response_shape(self, response_goal: Dict[str, Any]) -> str:
        return str(response_goal.get("response_shape") or "single_action")

    def _form_variant(self, response_goal: Dict[str, Any]) -> str:
        return str(response_goal.get("form_variant") or "default")

    def _clean_text(self, text: str) -> str:
        text = (text or "").strip()
        for pattern in self.INTERNAL_TEXT_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        for pattern in self.ROBOTIC_OPENING_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+([,.;:])", r"\1", text)
        text = re.sub(r"([,.;:])([^\s])", r"\1 \2", text)
        text = re.sub(r'([,.;:])[ \t]+(")', r"\1\2", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\.(\s*\.)+", ".", text)
        text = text.strip(" \n\t")
        if text and not re.search(r"[.!?]$", text):
            text += "."
        return text


def build_response(**kwargs: Any) -> Dict[str, Any]:
    return ResponseBuilder().build(**kwargs)
