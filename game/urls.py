from django.urls import path
from . import views as v

urlpatterns = [
    path("", v.landing, name="landing"),
    path("how-to-play/", v.how_to_play, name="how_to_play"),
    path("dashboard/", v.dashboard, name="dashboard"),
    path("report/", v.final_report, name="final_report"),
    path("api/status/", v.api_status, name="api_status"),
    path("case/<int:number>/", v.case_intro, name="case_intro"),
    path("case/<int:number>/start/", v.case_start, name="case_start"),
    path("case/<int:number>/investigate/", v.investigation, name="investigation"),
    path("case/<int:number>/evidence/<slug:key>/", v.evidence_view, name="evidence"),
    path("case/<int:number>/suspect/<slug:key>/", v.suspect_view, name="suspect"),
    path("case/<int:number>/deduce/", v.deduction, name="deduction"),
    path("case/<int:number>/results/", v.results, name="results"),
    path("case/<int:number>/reveal/", v.reveal, name="reveal"),
    path("api/case/<int:number>/ask/", v.api_ask, name="api_ask"),
    path("api/case/<int:number>/watson/", v.api_watson, name="api_watson"),
    path("api/case/<int:number>/hint/", v.api_hint, name="api_hint"),
    path("api/case/<int:number>/interrogate/", v.api_interrogate, name="api_interrogate"),
    path("api/case/<int:number>/explain/", v.api_explain, name="api_explain"),
    path("api/case/<int:number>/compare/", v.api_compare, name="api_compare"),
    path("api/case/<int:number>/evidence/<slug:key>/analysis/", v.api_evidence_analysis, name="api_evidence_analysis"),
    path("api/case/<int:number>/important/", v.api_important, name="api_important"),
    path("api/case/<int:number>/notebook/", v.api_notebook, name="api_notebook"),
]
