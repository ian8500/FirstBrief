from django.urls import path

from firstbrief.reporting import views

app_name = "reporting"

urlpatterns = [
    path("", views.catalogue, name="catalogue"),
    path("<str:report_code>/", views.criteria, name="criteria"),
    path("runs/<uuid:run_id>/", views.viewer, name="viewer"),
    path("runs/<uuid:run_id>/report.csv", views.export_csv, name="csv"),
    path("runs/<uuid:run_id>/report.pdf", views.export_pdf, name="pdf"),
]
