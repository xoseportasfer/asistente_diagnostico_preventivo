import os
import functools
import operator
import warnings
from typing import TypedDict, Annotated, Sequence
from dotenv import load_dotenv, find_dotenv

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from langchain_community.tools.tavily_search import TavilySearchResults

# 1. Configuración
warnings.filterwarnings("ignore")
load_dotenv(find_dotenv())

# Usamos Mistral (Temperatura 0 para máxima precisión y evitar "creatividad" médica)
llm = ChatOllama(model="mistral", temperature=0)
search_tool = [TavilySearchResults(max_results=3)]

# 2. Definición del Estado
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str

# 3. Orquestador de Flujo Clínico
def manager_node(state: AgentState):
    if not state["messages"]:
        return {"next": "recolector_sintomas"}
    
    last_msg = state["messages"][-1]
    last_actor = getattr(last_msg, "name", None)

    if last_actor == "recolector_sintomas":
        return {"next": "investigador_clinico"}
    if last_actor == "investigador_clinico":
        # CAMBIO AQUÍ: Debe ser 'redactor_markdown' para que coincida con el grafo
        return {"next": "redactor_markdown"} 
    if last_actor == "redactor_markdown":
        return {"next": "FINISH"}
    
    return {"next": "recolector_sintomas"}

# 4. Constructor de Nodos
def create_node(llm, tools, system_prompt, name):
    agent = create_react_agent(llm, tools, prompt=system_prompt)
    def node(state: AgentState):
        result = agent.invoke(state)
        return {
            "messages": [HumanMessage(content=result["messages"][-1].content, name=name)],
        }
    return node

# 5. Prompts Especializados (Enfoque Ético y Profesional)
recolector_prompt = (
    "Eres un Asistente de Anamnesis Médica. Tu función es escuchar la descripción de los síntomas "
    "del paciente y extraer de forma estructurada: tiempo de evolución, intensidad, factores que "
    "alivian o agravan y síntomas asociados. Sé empático pero profesional."
)

investigador_prompt = (
    "Eres un Investigador de Literatura Médica. Tu misión es buscar estudios, artículos científicos "
    "y guías clínicas relacionadas con los síntomas recopilados. ADVERTENCIA: No debes diagnosticar. "
    "Tu objetivo es proveer al médico información técnica sobre posibles patologías asociadas "
    "según la literatura médica actual."
)

redactor_prompt = (
    "Eres un Redactor de Informes Clínicos. Tu tarea es consolidar la información en un documento "
    "profesional para que un médico lo revise. Estructura el informe en: 1. Perfil del Paciente (Síntomas), "
    "2. Hallazgos en Literatura Médica, y 3. Puntos de atención sugeridos. "
    "Incluye un descargo de responsabilidad indicando que este informe es generado por IA para apoyo médico."
)

# Nodos
recolector_node = create_node(llm, [], recolector_prompt, "recolector_sintomas")
investigador_node = create_node(llm, search_tool, investigador_prompt, "investigador_clinico")
redactor_node = create_node(llm, [], redactor_prompt, "redactor_markdown")

# 6. Construcción del Grafo
workflow = StateGraph(AgentState)

workflow.add_node("manager", manager_node)
workflow.add_node("recolector_sintomas", recolector_node)
workflow.add_node("investigador_clinico", investigador_node)
workflow.add_node("redactor_markdown", redactor_node)

for node in ["recolector_sintomas", "investigador_clinico", "redactor_markdown"]:
    workflow.add_edge(node, "manager")

workflow.add_conditional_edges(
    "manager",
    lambda x: x["next"],
    {
        "recolector_sintomas": "recolector_sintomas",
        "investigador_clinico": "investigador_clinico",
        "redactor_markdown": "redactor_markdown", 
        "FINISH": END
    }
)

workflow.set_entry_point("manager")
health_app = workflow.compile()

# 7. Ejecución
if __name__ == "__main__":
    descripcion_paciente = "Hombre de 45 años con dolor punzante en el pecho tras hacer ejercicio, dura 10 minutos y se calma en reposo."
    inputs = {"messages": [HumanMessage(content=f"Preparar informe previo para el médico basado en: {descripcion_paciente}")]}
    
    print(f"--- Sistema de Soporte Clínico HealthTech ---")
    print(f"Entrada: {descripcion_paciente}\n" + "="*50)
    
    for s in health_app.stream(inputs, {"recursion_limit": 15}):
        if "__end__" not in s:
            node_name = list(s.keys())[0]
            if node_name != "manager":
                print(f"\n[FASE]: {node_name.upper()}")
                print(s[node_name]["messages"][-1].content)
                print("-" * 50)