# classes/views.py
import json
import re
from datetime import datetime

import google.generativeai as genai

from django.conf import settings as django_settings
from django.db import IntegrityError
from django.shortcuts import get_object_or_404

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework import status

from .models import Classroom, Student, Assignment, Grade, AttendanceSession, AttendanceRecord
from .serializers import (
    ClassroomListSerializer,
    ClassroomDetailSerializer,
    StudentSerializer,
    AssignmentSerializer,
    GradeSerializer,
)

genai.configure(api_key=django_settings.GEMINI_API_KEY)

_SCHOOL_YEAR_RE = re.compile(r'^\d{4}(-\d{4})?$')


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _detect_mime_type(filename: str, data: bytes) -> str:
    """
    Détermine le MIME type réel de l'image :
    1. Extension du nom de fichier
    2. Magic bytes (signature binaire)
    3. Fallback : image/jpeg
    """
    _EXT_MAP = {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
        'png': 'image/png', 'gif': 'image/gif',
        'webp': 'image/webp', 'heic': 'image/heic',
        'heif': 'image/heif',
    }

    # 1. Extension
    if filename:
        ext = filename.rsplit('.', 1)[-1].lower()
        if ext in _EXT_MAP:
            return _EXT_MAP[ext]

    # 2. Magic bytes
    if data[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'

    # 3. Fallback
    return 'image/jpeg'


# ─────────────────────────────────────────────
# OCR : extraction élèves depuis image
# ─────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def extract_students_from_image(request):
    """
    POST multipart : image → JSON liste d'élèves via Gemini.
    Champ attendu : image (fichier)
    """
    import time as _time
    t0 = _time.time()
    print(f"\n[OCR] ── Début extraction ──────────────────────")

    image_file = request.FILES.get('image')
    if not image_file:
        print("[OCR] ❌ Aucune image reçue dans la requête")
        return Response(
            {'success': False, 'message': 'Aucune image fournie.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    print(f"[OCR] 📎 Fichier reçu : {image_file.name} ({image_file.size} octets)")

    image_bytes = image_file.read()
    mime_type = _detect_mime_type(image_file.name, image_bytes)
    print(f"[OCR] 🔍 MIME détecté : {mime_type} | Taille bytes : {len(image_bytes)}")

    prompt = """Tu es un assistant OCR spécialisé dans l'extraction de listes d'élèves depuis des photos de documents scolaires (feuilles de présence, cahiers de texte, listes manuscrites ou imprimées).

Analyse cette image et extrais tous les noms et prénoms d'élèves visibles.

Retourne UNIQUEMENT un JSON valide, sans markdown, sans explication, avec ce format exact :
{
  "students": [
    {"first_name": "Prénom", "last_name": "NOM"},
    ...
  ],
  "confidence": "high",
  "notes": ""
}

Règles strictes :
- last_name en MAJUSCULES, first_name avec première lettre Majuscule
- Si tu ne peux pas distinguer nom et prénom, mets tout dans last_name et laisse first_name vide
- Ignore les numéros de liste, dates, matières et toute info non liée aux noms
- Confidence : "high" si liste claire, "medium" si partielle, "low" si peu lisible
- Si aucun élève détectable : {"students": [], "confidence": "low", "notes": "Image illisible ou vide"}
- Ne retourne que du JSON pur, pas de ```json``` ni de texte autour"""

    raw = None
    try:
        print(f"[OCR] ⚙️  Initialisation modèle Gemini...")
        model = genai.GenerativeModel('gemini-2.5-flash')
        image_part = {'mime_type': mime_type, 'data': image_bytes}

        print(f"[OCR] 🚀 Envoi à Gemini... (+{_time.time()-t0:.1f}s)")
        response = model.generate_content([prompt, image_part])
        t_gemini = _time.time() - t0
        print(f"[OCR] ✅ Réponse Gemini reçue (+{t_gemini:.1f}s)")

        # Détails de la réponse Gemini
        try:
            print(f"[OCR] 📊 Usage tokens — prompt: {response.usage_metadata.prompt_token_count} | réponse: {response.usage_metadata.candidates_token_count} | total: {response.usage_metadata.total_token_count}")
        except Exception:
            pass
        try:
            finish = response.candidates[0].finish_reason
            print(f"[OCR] 🏁 finish_reason: {finish}")
            if str(finish) not in ('FinishReason.STOP', '1', 'STOP'):
                print(f"[OCR] ⚠️  finish_reason anormal — la réponse est peut-être tronquée ou bloquée")
        except Exception:
            pass
        try:
            safety = response.candidates[0].safety_ratings
            blocked = [r for r in safety if str(r.probability) not in ('HarmProbability.NEGLIGIBLE', '1', 'NEGLIGIBLE')]
            if blocked:
                print(f"[OCR] 🛡️  Safety flags : {blocked}")
            else:
                print(f"[OCR] 🛡️  Safety OK — aucun contenu bloqué")
        except Exception:
            pass

        raw = response.text.strip()
        print(f"[OCR] 📝 Réponse brute ({len(raw)} chars) : {raw[:200]}{'...' if len(raw) > 200 else ''}")

        # Nettoyage au cas où Gemini ajoute des backticks malgré tout
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
            print(f"[OCR] 🧹 Backticks supprimés")

        data = json.loads(raw)
        nb = len(data.get('students', []))
        print(f"[OCR] ✅ {nb} élève(s) extrait(s) | confidence={data.get('confidence')} | durée totale={_time.time()-t0:.1f}s")
        print(f"[OCR] ────────────────────────────────────────────\n")
        return Response({'success': True, **data})

    except json.JSONDecodeError:
        print(f"[OCR] ❌ JSONDecodeError — réponse non parseable : {raw}")
        return Response(
            {'success': False, 'message': 'Réponse IA non parseable.', 'raw': raw},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
    except Exception as e:
        print(f"[OCR] ❌ Exception après {_time.time()-t0:.1f}s : {type(e).__name__}: {e}")
        return Response(
            {'success': False, 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ─────────────────────────────────────────────
# CLASSES (Classroom)
# ─────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def classrooms(request):
    """GET : liste des classes. POST : créer une classe."""
    if request.method == 'GET':
        qs = Classroom.objects.filter(teacher=request.user).prefetch_related('students', 'assignments')
        return Response({'success': True, 'classrooms': ClassroomListSerializer(qs, many=True).data})

    # POST
    data = request.data
    name = data.get('name', '').strip()
    subject = data.get('subject', '').strip()
    school_name = data.get('school_name', '').strip()
    school_year = data.get('school_year', '2024-2025').strip()

    if not name or not subject:
        return Response(
            {'success': False, 'message': 'Nom et matière requis.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if school_year and not _SCHOOL_YEAR_RE.match(school_year):
        return Response(
            {'success': False, 'message': "Format d'année scolaire invalide (ex: 2024-2025 ou 2025)."},
            status=status.HTTP_400_BAD_REQUEST
        )

    classroom = Classroom.objects.create(
        teacher=request.user,
        name=name,
        subject=subject,
        school_name=school_name,
        school_year=school_year,
    )

    # Ajout optionnel d'élèves en lot à la création (après OCR)
    students_data = data.get('students', [])
    if students_data:
        to_create = []
        for s in students_data:
            fn = s.get('first_name', '').strip()[:100]
            ln = s.get('last_name', '').strip()[:100]
            if ln:
                to_create.append(Student(classroom=classroom, first_name=fn, last_name=ln))
        Student.objects.bulk_create(to_create, ignore_conflicts=True)

    return Response(
        {'success': True, 'classroom': ClassroomDetailSerializer(classroom).data},
        status=status.HTTP_201_CREATED
    )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def classroom_detail(request, classroom_id):
    """GET / PUT / DELETE d'une classe."""
    classroom = get_object_or_404(Classroom, id=classroom_id, teacher=request.user)

    if request.method == 'GET':
        return Response({
            'success': True,
            'classroom': ClassroomDetailSerializer(classroom).data
        })

    if request.method == 'PUT':
        data = request.data
        new_year = data.get('school_year', classroom.school_year).strip()
        if 'school_year' in data and new_year and not _SCHOOL_YEAR_RE.match(new_year):
            return Response(
                {'success': False, 'message': "Format d'année scolaire invalide (ex: 2024-2025 ou 2025)."},
                status=status.HTTP_400_BAD_REQUEST
            )
        classroom.name = data.get('name', classroom.name).strip()
        classroom.subject = data.get('subject', classroom.subject).strip()
        classroom.school_name = data.get('school_name', classroom.school_name).strip()
        classroom.school_year = new_year
        classroom.save()
        return Response({'success': True, 'classroom': ClassroomDetailSerializer(classroom).data})

    # DELETE
    classroom.delete()
    return Response({'success': True, 'message': 'Classe supprimée.'})


# ─────────────────────────────────────────────
# ÉLÈVES (Student)
# ─────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_students(request, classroom_id):
    """
    POST : ajouter un ou plusieurs élèves à une classe.
    Body : {"students": [{"first_name": "...", "last_name": "..."}]}
    Ou un seul : {"first_name": "...", "last_name": "..."}
    """
    classroom = get_object_or_404(Classroom, id=classroom_id, teacher=request.user)
    data = request.data

    students_data = data.get('students')
    if students_data is None:
        # Ajout individuel
        first_name = data.get('first_name', '').strip()[:100]
        last_name = data.get('last_name', '').strip()[:100]
        if not last_name:
            return Response(
                {'success': False, 'message': 'Le nom de famille est requis.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            student = Student.objects.create(
                classroom=classroom, first_name=first_name, last_name=last_name
            )
        except IntegrityError:
            return Response(
                {'success': False, 'message': 'Cet élève existe déjà dans cette classe.'},
                status=status.HTTP_409_CONFLICT
            )
        return Response(
            {'success': True, 'student': StudentSerializer(student).data},
            status=status.HTTP_201_CREATED
        )

    # Ajout en lot — validation + ignore doublons
    to_create = []
    for s in students_data:
        fn = s.get('first_name', '').strip()[:100]
        ln = s.get('last_name', '').strip()[:100]
        if ln:
            to_create.append(Student(classroom=classroom, first_name=fn, last_name=ln))
    created = Student.objects.bulk_create(to_create, ignore_conflicts=True)
    return Response(
        {'success': True, 'created': len(created), 'students': StudentSerializer(
            classroom.students.all(), many=True
        ).data},
        status=status.HTTP_201_CREATED
    )


@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def student_detail(request, student_id):
    """PUT : modifier un élève. DELETE : supprimer."""
    student = get_object_or_404(Student, id=student_id, classroom__teacher=request.user)

    if request.method == 'PUT':
        student.first_name = request.data.get('first_name', student.first_name).strip()
        student.last_name = request.data.get('last_name', student.last_name).strip()
        student.save()
        return Response({'success': True, 'student': StudentSerializer(student).data})

    student.delete()
    return Response({'success': True, 'message': 'Élève supprimé.'})


# ─────────────────────────────────────────────
# DEVOIRS (Assignment)
# ─────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def assignments(request, classroom_id):
    """GET : liste des devoirs. POST : créer un devoir."""
    classroom = get_object_or_404(Classroom, id=classroom_id, teacher=request.user)

    if request.method == 'GET':
        qs = classroom.assignments.all()
        return Response({'success': True, 'assignments': AssignmentSerializer(qs, many=True).data})

    data = request.data
    name = data.get('name', '').strip()
    date = data.get('date')
    if not name or not date:
        return Response(
            {'success': False, 'message': 'Nom et date requis.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Bug #19 — Validation format date
    try:
        datetime.strptime(str(date), '%Y-%m-%d')
    except (ValueError, TypeError):
        return Response(
            {'success': False, 'message': 'Format de date invalide (YYYY-MM-DD attendu).'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Bugs #15 & #21 — Validation valeurs numériques
    try:
        coefficient = float(data.get('coefficient', 1.0))
        max_score = float(data.get('max_score', 20.0))
        global_bonus = float(data.get('global_bonus', 0.0))
    except (TypeError, ValueError):
        return Response(
            {'success': False, 'message': 'Valeurs numériques invalides.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if coefficient <= 0:
        return Response(
            {'success': False, 'message': 'Le coefficient doit être supérieur à 0.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if max_score <= 0:
        return Response(
            {'success': False, 'message': 'Le barème doit être supérieur à 0.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if global_bonus < 0:
        return Response(
            {'success': False, 'message': 'Le bonus ne peut pas être négatif.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if global_bonus > max_score:
        return Response(
            {'success': False, 'message': 'Le bonus ne peut pas dépasser le barème.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    assignment = Assignment.objects.create(
        classroom=classroom,
        name=name,
        assignment_type=data.get('assignment_type', 'devoir'),
        date=date,
        coefficient=coefficient,
        max_score=max_score,
        global_bonus=global_bonus,
    )
    return Response(
        {'success': True, 'assignment': AssignmentSerializer(assignment).data},
        status=status.HTTP_201_CREATED
    )


@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def assignment_detail(request, assignment_id):
    """PUT : modifier un devoir. DELETE : supprimer."""
    assignment = get_object_or_404(
        Assignment, id=assignment_id, classroom__teacher=request.user
    )

    if request.method == 'PUT':
        data = request.data
        new_date = data.get('date', assignment.date)
        # Bug #19 — Validation format date si modifiée
        if 'date' in data:
            try:
                datetime.strptime(str(new_date), '%Y-%m-%d')
            except (ValueError, TypeError):
                return Response(
                    {'success': False, 'message': 'Format de date invalide (YYYY-MM-DD attendu).'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        # Bugs #15 & #21 — Validation valeurs numériques
        try:
            coefficient = float(data.get('coefficient', assignment.coefficient))
            max_score = float(data.get('max_score', assignment.max_score))
            global_bonus = float(data.get('global_bonus', assignment.global_bonus))
        except (TypeError, ValueError):
            return Response(
                {'success': False, 'message': 'Valeurs numériques invalides.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if coefficient <= 0:
            return Response(
                {'success': False, 'message': 'Le coefficient doit être supérieur à 0.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if max_score <= 0:
            return Response(
                {'success': False, 'message': 'Le barème doit être supérieur à 0.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if global_bonus < 0:
            return Response(
                {'success': False, 'message': 'Le bonus ne peut pas être négatif.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if global_bonus > max_score:
            return Response(
                {'success': False, 'message': 'Le bonus ne peut pas dépasser le barème.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        assignment.name = data.get('name', assignment.name).strip()
        assignment.assignment_type = data.get('assignment_type', assignment.assignment_type)
        assignment.date = new_date
        assignment.coefficient = coefficient
        assignment.max_score = max_score
        assignment.global_bonus = global_bonus
        assignment.save()
        return Response({'success': True, 'assignment': AssignmentSerializer(assignment).data})

    assignment.delete()
    return Response({'success': True, 'message': 'Devoir supprimé.'})


# ─────────────────────────────────────────────
# NOTES (Grade)
# ─────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def grades(request, assignment_id):
    """
    GET : notes du devoir avec la liste de tous les élèves (absents inclus).
    POST : saisir / mettre à jour les notes en batch.
      Body: {"grades": [{"student_id": 1, "score": 14.5, "comment": ""}, ...]}
      Pour appliquer une note globale : {"global_score": 15, "global_comment": ""}
    """
    assignment = get_object_or_404(
        Assignment, id=assignment_id, classroom__teacher=request.user
    )
    classroom = assignment.classroom

    if request.method == 'GET':
        students = classroom.students.all()
        grade_map = {g.student_id: g for g in assignment.grades.all()}
        result = []
        for s in students:
            g = grade_map.get(s.id)
            result.append({
                'student_id': s.id,
                'student_name': s.full_name,
                'score': g.score if g else None,
                'effective_score': g.effective_score if g else None,
                'comment': g.comment if g else '',
                'grade_id': g.id if g else None,
            })
        return Response({
            'success': True,
            'assignment': AssignmentSerializer(assignment).data,
            'grades': result,
        })

    # POST — saisie batch
    data = request.data
    global_score = data.get('global_score')
    global_comment = data.get('global_comment', '')

    if global_score is not None:
        # Note globale pour toute la classe
        students = classroom.students.all()
        for s in students:
            Grade.objects.update_or_create(
                student=s,
                assignment=assignment,
                defaults={'score': float(global_score), 'comment': global_comment}
            )
        return Response({'success': True, 'message': f'Note globale {global_score} appliquée.'})

    grades_data = data.get('grades', [])
    if not grades_data:
        return Response(
            {'success': False, 'message': 'Aucune note fournie.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    updated = 0
    for entry in grades_data:
        student_id = entry.get('student_id')
        score = entry.get('score')  # None = absent
        comment = entry.get('comment', '')
        if not student_id:
            continue
        student = get_object_or_404(Student, id=student_id, classroom=classroom)
        Grade.objects.update_or_create(
            student=student,
            assignment=assignment,
            defaults={'score': score, 'comment': comment}
        )
        updated += 1

    return Response({'success': True, 'updated': updated})


# ─────────────────────────────────────────────
# RAPPORT (Bulletin de notes)
# ─────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def classroom_report(request, classroom_id):
    """
    Retourne le bulletin complet : liste élèves × devoirs avec toutes les notes
    et les moyennes calculées.
    """
    classroom = get_object_or_404(Classroom, id=classroom_id, teacher=request.user)
    students = list(classroom.students.all())
    assignments_qs = list(classroom.assignments.all())

    # Map student_id → assignment_id → grade
    all_grades = Grade.objects.filter(
        assignment__classroom=classroom
    ).select_related('student', 'assignment')
    grade_map = {}
    for g in all_grades:
        grade_map.setdefault(g.student_id, {})[g.assignment_id] = g

    student_rows = []
    for s in students:
        grades_row = {}
        for a in assignments_qs:
            g = grade_map.get(s.id, {}).get(a.id)
            if g:
                effective = min(
                    max((g.score or 0) + a.global_bonus, 0), a.max_score
                ) if g.score is not None else None
            else:
                effective = None
            grades_row[str(a.id)] = {
                'score': g.score if g else None,
                'effective_score': effective,
                'comment': g.comment if g else '',
            }
        student_rows.append({
            'id': s.id,
            'full_name': s.full_name,
            'first_name': s.first_name,
            'last_name': s.last_name,
            'average': s.average() or 0,
            'grades': grades_row,
        })

    # Tri par moyenne décroissante
    student_rows.sort(key=lambda r: (r['average'] or -1), reverse=True)
    # Rang
    for i, row in enumerate(student_rows):
        row['rank'] = i + 1 if row['average'] is not None else None

    return Response({
        'success': True,
        'classroom': {
            'id': classroom.id,
            'name': classroom.name,
            'subject': classroom.subject,
            'school_year': classroom.school_year,
            'class_average': classroom.class_average() or 0,
        },
        'assignments': AssignmentSerializer(assignments_qs, many=True).data,
        'students': student_rows,
    })


# ─────────────────────────────────────────────
# PRÉSENCE (AttendanceSession)
# ─────────────────────────────────────────────

def _session_to_dict(session, include_records=False):
    """Sérialise une séance en dict."""
    # date et time peuvent être des str ou des objets Python selon le contexte
    date = session.date
    time = session.time
    date_str = date.isoformat() if hasattr(date, 'isoformat') else str(date)
    time_str = time.strftime('%H:%M') if hasattr(time, 'strftime') else str(time)[:5]

    d = {
        'id': session.id,
        'date': date_str,
        'time': time_str,
        'label': session.label,
        'present_count': session.present_count,
        'absent_count': session.absent_count,
        'total_count': session.total_count,
        'created_at': session.created_at.isoformat(),
    }
    if include_records:
        d['records'] = [
            {
                'student_id': r.student.id,
                'student_name': r.student.full_name,
                'is_present': r.is_present,
            }
            for r in session.records.select_related('student').order_by(
                'student__last_name', 'student__first_name'
            )
        ]
    return d


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def attendance_sessions(request, classroom_id):
    """
    GET  : liste des séances d'appel de la classe.
    POST : créer une séance + pré-remplir tous les élèves (présents par défaut).
    """
    classroom = get_object_or_404(Classroom, id=classroom_id, teacher=request.user)

    if request.method == 'GET':
        sessions = classroom.attendance_sessions.prefetch_related('records')
        return Response({
            'success': True,
            'sessions': [_session_to_dict(s) for s in sessions],
        })

    # POST — créer une séance
    data = request.data
    date = data.get('date')
    time = data.get('time')
    label = data.get('label', '').strip()

    if not date or not time:
        return Response(
            {'success': False, 'message': 'Date et heure requises.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Bug #19 — Validation format date
    try:
        datetime.strptime(str(date), '%Y-%m-%d')
    except (ValueError, TypeError):
        return Response(
            {'success': False, 'message': 'Format de date invalide (YYYY-MM-DD attendu).'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Bug #20 — Validation format heure
    if not re.match(r'^\d{2}:\d{2}(:\d{2})?$', str(time)):
        return Response(
            {'success': False, 'message': "Format d'heure invalide (HH:MM attendu)."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Bug #22 — Éviter les doublons de séance
    if AttendanceSession.objects.filter(classroom=classroom, date=date, time=str(time)[:5]).exists():
        return Response(
            {'success': False, 'message': 'Une séance existe déjà pour cette classe à cette date et heure.'},
            status=status.HTTP_409_CONFLICT
        )

    session = AttendanceSession.objects.create(
        classroom=classroom,
        date=date,
        time=time,
        label=label,
    )

    # Pré-remplir avec tous les élèves — présents par défaut
    students = classroom.students.all()
    AttendanceRecord.objects.bulk_create([
        AttendanceRecord(session=session, student=s, is_present=True)
        for s in students
    ])

    return Response(
        {'success': True, 'session': _session_to_dict(session, include_records=True)},
        status=status.HTTP_201_CREATED
    )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def attendance_session_detail(request, session_id):
    """
    GET    : détail séance + liste élèves avec statut.
    PUT    : mise à jour des présences (batch) + métadonnées optionnelles.
    DELETE : supprimer la séance.
    """
    session = get_object_or_404(
        AttendanceSession, id=session_id, classroom__teacher=request.user
    )

    if request.method == 'GET':
        return Response({'success': True, 'session': _session_to_dict(session, include_records=True)})

    if request.method == 'PUT':
        # Mise à jour des présences
        records_data = request.data.get('records', [])
        for entry in records_data:
            student_id = entry.get('student_id')
            is_present = entry.get('is_present', True)
            session.records.filter(student_id=student_id).update(is_present=is_present)

        # Métadonnées optionnelles
        if 'label' in request.data:
            session.label = request.data['label'].strip()
        if 'date' in request.data:
            session.date = request.data['date']
        if 'time' in request.data:
            session.time = request.data['time']
        session.save()

        # Retourne la séance mise à jour avec les records frais
        session.refresh_from_db()
        return Response({'success': True, 'session': _session_to_dict(session, include_records=True)})

    # DELETE
    session.delete()
    return Response({'success': True, 'message': 'Séance supprimée.'})


# ─────────────────────────────────────────────
# STATISTIQUES
# ─────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def classroom_stats(request, classroom_id):
    """Stats globales de la classe."""
    classroom = get_object_or_404(Classroom, id=classroom_id, teacher=request.user)
    students = list(classroom.students.all())
    assignments_qs = list(classroom.assignments.order_by('date'))

    # Moyennes par élève
    averages = [(s, s.average()) for s in students]
    averages_with_score = [(s, a) for s, a in averages if a is not None]

    best = max(averages_with_score, key=lambda x: x[1], default=None)
    worst = min(averages_with_score, key=lambda x: x[1], default=None)

    # Distribution /20
    distribution = {'below_10': 0, 'between_10_14': 0, 'above_14': 0, 'no_grade': 0}
    for _, avg in averages:
        if avg is None:
            distribution['no_grade'] += 1
        elif avg < 10:
            distribution['below_10'] += 1
        elif avg < 14:
            distribution['between_10_14'] += 1
        else:
            distribution['above_14'] += 1

    # Taux de présence global
    total_sessions = classroom.attendance_sessions.count()
    attendance_rate = None
    if total_sessions > 0:
        total_records = AttendanceRecord.objects.filter(session__classroom=classroom).count()
        total_present = AttendanceRecord.objects.filter(session__classroom=classroom, is_present=True).count()
        attendance_rate = round(total_present / total_records * 100, 1) if total_records > 0 else None

    # Classement
    sorted_students = sorted(averages, key=lambda x: (x[1] or -1), reverse=True)
    ranking = [
        {
            'id': s.id,
            'full_name': s.full_name,
            'average': avg or 0,
            'rank': i + 1 if avg is not None else None,
        }
        for i, (s, avg) in enumerate(sorted_students)
    ]

    # Stats par devoir (moyenne normalisée /20)
    assignment_stats = []
    for a in assignments_qs:
        graded = a.grades.filter(score__isnull=False)
        avg_norm = None
        if graded.exists() and a.max_score > 0:
            normalized = [
                round(min(max((g.score + a.global_bonus) / a.max_score * 20, 0), 20), 2)
                for g in graded
            ]
            avg_norm = round(sum(normalized) / len(normalized), 2)
        assignment_stats.append({
            'id': a.id,
            'name': a.name,
            'date': a.date.isoformat(),
            'assignment_type': a.assignment_type,
            'coefficient': a.coefficient,
            'max_score': a.max_score,
            'class_average_normalized': avg_norm,
            'class_average_raw': a.class_average,
            'graded_count': a.graded_count,
        })

    return Response({
        'success': True,
        'stats': {
            'total_students': len(students),
            'total_assignments': len(assignments_qs),
            'total_sessions': total_sessions,
            'class_average': classroom.class_average() or 0,
            'attendance_rate': attendance_rate,
            'best_student': {
                'id': best[0].id, 'full_name': best[0].full_name, 'average': best[1] or 0
            } if best else None,
            'worst_student': {
                'id': worst[0].id, 'full_name': worst[0].full_name, 'average': worst[1] or 0
            } if worst else None,
            'distribution': distribution,
            'ranking': ranking,
            'assignment_stats': assignment_stats,
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_stats(request, student_id):
    """Stats individuelles d'un élève."""
    student = get_object_or_404(Student, id=student_id, classroom__teacher=request.user)
    classroom = student.classroom

    # Moyenne + rang
    all_avgs = sorted(
        [(s, s.average()) for s in classroom.students.all()],
        key=lambda x: (x[1] or -1), reverse=True
    )
    student_avg = student.average()
    rank = None
    total_ranked = sum(1 for _, a in all_avgs if a is not None)
    for i, (s, avg) in enumerate(all_avgs):
        if s.id == student.id and avg is not None:
            rank = i + 1

    # Notes par devoir (ordre chronologique)
    assignments_qs = list(classroom.assignments.order_by('date'))
    grade_map = {g.assignment_id: g for g in student.grades.select_related('assignment')}

    grades_detail = []
    for a in assignments_qs:
        g = grade_map.get(a.id)
        score = g.score if g else None
        effective = normalized = None
        if score is not None and a.max_score > 0:
            effective = round(min(max(score + a.global_bonus, 0), a.max_score), 2)
            normalized = round((effective / a.max_score) * 20, 2)
        grades_detail.append({
            'assignment_id': a.id,
            'assignment_name': a.name,
            'assignment_type': a.assignment_type,
            'date': a.date.isoformat(),
            'coefficient': a.coefficient,
            'max_score': a.max_score,
            'score': score,
            'effective_score': effective,
            'normalized_score': normalized,
            'class_average_raw': a.class_average,
        })

    scored = [g for g in grades_detail if g['normalized_score'] is not None]
    best_grade = max(scored, key=lambda g: g['normalized_score'], default=None)
    worst_grade = min(scored, key=lambda g: g['normalized_score'], default=None)

    # Tendance sur les 3 derniers devoirs notés
    last_3 = [g['normalized_score'] for g in scored[-3:]]
    trend = 'stable'
    if len(last_3) >= 2:
        if last_3[-1] > last_3[0] + 1:
            trend = 'up'
        elif last_3[-1] < last_3[0] - 1:
            trend = 'down'

    # Présences
    total_sessions = classroom.attendance_sessions.count()
    present_count = AttendanceRecord.objects.filter(
        session__classroom=classroom, student=student, is_present=True
    ).count()
    absent_count = AttendanceRecord.objects.filter(
        session__classroom=classroom, student=student, is_present=False
    ).count()
    attendance_rate = round(present_count / total_sessions * 100, 1) if total_sessions > 0 else None

    return Response({
        'success': True,
        'student': {
            'id': student.id,
            'full_name': student.full_name,
            'first_name': student.first_name,
            'last_name': student.last_name,
            'classroom_name': classroom.name,
            'subject': classroom.subject,
            'school_name': classroom.school_name,
        },
        'stats': {
            'average': student_avg or 0,
            'rank': rank,
            'total_students': len(all_avgs),
            'total_ranked': total_ranked,
            'trend': trend,
            'total_sessions': total_sessions,
            'present_count': present_count,
            'absent_count': absent_count,
            'attendance_rate': attendance_rate,
            'grades': grades_detail,
            'best_grade': best_grade,
            'worst_grade': worst_grade,
        },
    })
