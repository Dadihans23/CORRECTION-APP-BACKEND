# classes/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # OCR
    path('extract-students/', views.extract_students_from_image, name='extract-students'),

    # Classrooms
    path('', views.classrooms, name='classrooms'),
    path('<int:classroom_id>/', views.classroom_detail, name='classroom-detail'),

    # Students
    path('<int:classroom_id>/students/', views.add_students, name='add-students'),
    path('students/<int:student_id>/', views.student_detail, name='student-detail'),

    # Assignments
    path('<int:classroom_id>/assignments/', views.assignments, name='assignments'),
    path('assignments/<int:assignment_id>/', views.assignment_detail, name='assignment-detail'),

    # Grades
    path('assignments/<int:assignment_id>/grades/', views.grades, name='grades'),

    # Report
    path('<int:classroom_id>/report/', views.classroom_report, name='classroom-report'),

    # Attendance
    path('<int:classroom_id>/attendance/', views.attendance_sessions, name='attendance-sessions'),
    path('attendance/<int:session_id>/', views.attendance_session_detail, name='attendance-session-detail'),

    # Stats
    path('<int:classroom_id>/stats/', views.classroom_stats, name='classroom-stats'),
    path('students/<int:student_id>/stats/', views.student_stats, name='student-stats'),
]
