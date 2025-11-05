

import logging
import google.generativeai as genai
from django.conf import settings
import json
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from rest_framework.response import Response
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from datetime import datetime
from rest_framework.permissions import IsAuthenticated
from .models import CorrectionHistory  , ChatMessage  , ChatSession , ImageCorrection# Import du modèle
from .serializers import CorrectionHistorySerializer , ChatMessageSerializer , ChatSessionDetailSerializer , ImageCorrectionSerializer
from subscriptions.models import   UsageLog , Subscription   # Import du modèle

import google.generativeai as genai
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


from rest_framework.decorators import api_view, schema




# backend/views.py
import google.generativeai as genai
from django.conf import settings
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated




# backend/views.py
# backend/views.py
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import ChatSession, ChatMessage
from .serializers import ChatSessionDetailSerializer , ChatMessageSerializer
from django.conf import settings



logger = logging.getLogger(__name__)
genai.configure(api_key=settings.GEMINI_API_KEY)

class ProcessImageView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    LITERARY_DOMAINS = [
        'Français', 'Histoire-Géographie', 'Philosophie', 
        'Langues étrangères', 'Autre'
    ]
    
    SENSITIVE_TYPES = [
        'Exercice de rédaction', 'Analyse de texte'
    ]
    
    SCIENTIFIC_DOMAINS = [
        'Mathématiques', 'Physique-Chimie', 'SVT', 
        'Informatique', 'Économie / SES'
    ]
    EDUCATIONAL_LEVELS = [
        'Lycée – Terminale', 'Lycée – Première', 'Lycée – Seconde',
        'Collège (6ᵉ – 3ᵉ)', 'Supérieur – BTS / DUT', 'Supérieur – Licence'
    ]

    def post(self, request):
        TEST_MODE = False
        if TEST_MODE:
            image_path = r'C:\git_project\CORRECTION APP BACKEND\treatment\images\testsvt.jpg'
            context_str = json.dumps({
                'domaine': 'Général',
                'niveau': 'Lycée – Terminale',
                'type_exercice': 'Problème à résoudre',
                'attente': 'Solution étape par étape',
                'infos': ''
            })
            try:
                with open(image_path, 'rb') as f:
                    image_bytes = f.read()
            except FileNotFoundError:
                logger.error(f"Image locale non trouvée: {image_path}")
                return Response(
                    {'success': False, 'message': f'Image locale non trouvée: {image_path}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            image = request.FILES.get('image')
            context_str = request.POST.get('context')

            if not image:
                return Response(
                    {'success': False, 'message': 'Aucune image fournie.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            image_bytes = image.read()

        try:
            context = json.loads(context_str) if context_str else {}
            domaine = context.get('domaine', 'Mathématiques')
            niveau = context.get('niveau', 'Collège (6ᵉ – 3ᵉ)')
            type_exercice = context.get('type_exercice', 'Problème à résoudre')
            attente = context.get('attente', 'Solution étape par étape')
            infos = context.get('infos', '')

            logger.info(f"Contexte: Domaine={domaine}, Type={type_exercice}, Niveau={niveau}")

            # EXTRACTION INITIALE DU TEXTE POUR FALLBACK
            extracted_text = self._extract_text(image_bytes)

            # ANALYSE INITIALE DE LA BRANCHE PAR L'IA
            branch_analysis = self._detect_branch(image_bytes, extracted_text)

            # VÉRIFICATION DE L'INCOHÉRENCE DOMAINE/BRANCHE
            detected_branch = branch_analysis['branch']
            detected_domain = branch_analysis['detected_domain']
            domain_mismatch = None
            if domaine != detected_domain:
                domain_mismatch = (
                    f"L'utilisateur a indiqué '{domaine}', mais l'exercice est détecté comme "
                    f"'{detected_domain}' ({detected_branch})."
                )

            # ANALYSE DU TYPE DE CONTENU
            content_analysis = self._analyze_content_type_with_education(
                detected_domain, type_exercice, attente, niveau
            )

            ia_response = self.call_gemini_api(
                image_bytes, detected_domain, niveau, type_exercice,
                attente, infos, content_analysis
            )

            # ← CORRECTION : extraire le texte AVANT de construire response_data
            extracted_text_final = ia_response.get('extracted_text', extracted_text)

            # DATE/HEURE BACKEND
            current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # CONSTRUCTION DE LA RÉPONSE
            response_data = {
                'success': True,
                'data': {
                    'user_domain': domaine,
                    'user_level': niveau,
                    'user_exercise_type': type_exercice,
                    'user_expectation': attente,
                    'user_info': infos,
                    'detected_branch': detected_branch,
                    'detected_branch_explanation': branch_analysis['explanation'],
                    'domain_mismatch': domain_mismatch,
                    'response_datetime': current_datetime,
                    'extracted_text': extracted_text_final,          # ← SÛR
                    'solution': {
                        'result': ia_response.get('result', ''),
                        'steps': ia_response.get('steps', [])
                    }
                },
                'content_type': content_analysis['type'],
                'educational_mode': content_analysis.get('educational_mode', False)
            }

            # GESTION DES ERREURS DE GEMINI (ex. COPYRIGHT_BLOCK)
            if not ia_response.get('success', True):
                if ia_response.get('error_type') == 'COPYRIGHT_BLOCK':
                    ia_response = self._educational_fallback(
                        detected_domain, type_exercice, niveau, content_analysis
                    )
                    # Recalcul du texte en mode fallback
                    extracted_text_final = ia_response.get(
                        'extracted_text',
                        f"Mode pédagogique - {domaine}"
                    )

                if not ia_response.get('success', True):
                    response_data = {
                        'success': False,
                        'message': ia_response['message'],
                        'data': {
                            'user_domain': domaine,
                            'user_level': niveau,
                            'user_exercise_type': type_exercice,
                            'user_expectation': attente,
                            'user_info': infos,
                            'solution': None,
                            'detected_branch': detected_branch,
                            'detected_branch_explanation': branch_analysis['explanation'],
                            'domain_mismatch': domain_mismatch,
                            'extracted_text': extracted_text_final  # ← Toujours présent
                        },
                        'content_type': content_analysis['type'],
                    }

            # SAUVEGARDE DANS L'HISTORIQUE (utilise extracted_text_final)
            CorrectionHistory.objects.create(
                user=request.user,
                user_domain=domaine,
                user_level=niveau,
                user_exercise_type=type_exercice,
                user_expectation=attente,
                user_info=infos,
                detected_branch=detected_branch,
                detected_branch_explanation=branch_analysis['explanation'],
                domain_mismatch=domain_mismatch,
                response_datetime=current_datetime,
                extracted_text=extracted_text_final,               # ← CORRECTION
                solution=response_data['data'].get('solution'),   # .get() pour éviter KeyError
                content_type=content_analysis['type'],
                educational_mode=content_analysis.get('educational_mode', False),
                success=response_data['success'],
                error_message=response_data.get('message')
            )

            return Response(response_data)

        except json.JSONDecodeError:
            # ← CORRECTION : même logique pour les erreurs de parsing
            extracted_text_final = extracted_text
            current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            response_data = {
                'success': False,
                'message': 'Contexte invalide.',
                'data': {
                    'user_domain': domaine,
                    'user_level': niveau,
                    'user_exercise_type': type_exercice,
                    'user_expectation': attente,
                    'user_info': infos,
                    'extracted_text': extracted_text_final
                }
            }
            CorrectionHistory.objects.create(
                user=request.user,
                user_domain=domaine,
                user_level=niveau,
                user_exercise_type=type_exercice,
                user_expectation=attente,
                user_info=infos,
                success=False,
                error_message='Contexte invalide.',
                extracted_text=extracted_text_final
            )
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Erreur: {str(e)}")
            extracted_text_final = extracted_text
            current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            response_data = {
                'success': False,
                'message': f'Erreur serveur: {str(e)}',
                'data': {
                    'user_domain': domaine,
                    'user_level': niveau,
                    'user_exercise_type': type_exercice,
                    'user_expectation': attente,
                    'user_info': infos,
                    'extracted_text': extracted_text_final
                }
            }
            CorrectionHistory.objects.create(
                user=request.user,
                user_domain=domaine,
                user_level=niveau,
                user_exercise_type=type_exercice,
                user_expectation=attente,
                user_info=infos,
                success=False,
                error_message=f'Erreur serveur: {str(e)}',
                extracted_text=extracted_text_final
            )
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _extract_text(self, image_bytes):
        """Extrait le texte de l'image pour fallback"""
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            image_part = {'mime_type': 'image/jpeg', 'data': image_bytes}
            prompt = "Extrayez le texte brut de l'image sans interprétation."
            response = model.generate_content([prompt, image_part], generation_config={"temperature": 0.1})
            return response.text.strip()[:1000]  # Limite pour éviter surcharge
        except Exception as e:
            logger.error(f"Erreur extraction texte: {str(e)}")
            return ""

    def _detect_branch(self, image_bytes, extracted_text):
        """Analyse l'image et le texte extrait pour détecter la branche"""
        model = genai.GenerativeModel('gemini-2.5-flash')
        try:
            image_part = {'mime_type': 'image/jpeg', 'data': image_bytes}
            prompt = f"""
Analyse l'image et le texte suivant pour déterminer si l'exercice est SCIENTIFIQUE (Mathématiques, Physique-Chimie, SVT, Informatique, Économie/SES) ou LITTÉRAIRE (Français, Histoire-Géographie, Philosophie, Langues étrangères, Autre).
Texte extrait : {extracted_text[:1000]}
Retourne un JSON avec :
- "branch": "Scientifique" ou "Littéraire"
- "detected_domain": Le domaine spécifique (ex. "Anglais", "Mathématiques")
- "explanation": Une courte explication de la détection

JSON :
{{
  "branch": "Scientifique ou Littéraire",
  "detected_domain": "Domaine détecté",
  "explanation": "Explication de la détection"
}}
"""
            response = model.generate_content([prompt, image_part], generation_config={"temperature": 0.2})
            content = response.text.strip()
            try:
                result = json.loads(content)
                return {
                    'branch': result.get('branch', 'Général'),
                    'detected_domain': result.get('detected_domain', 'Général'),
                    'explanation': result.get('explanation', 'Analyse non concluante.')
                }
            except json.JSONDecodeError:
                # Fallback : Analyse du texte extrait
                return self._fallback_branch_detection(extracted_text)
        except Exception as e:
            logger.error(f"Erreur détection branche: {str(e)}")
            return self._fallback_branch_detection(extracted_text)

    def _fallback_branch_detection(self, extracted_text):
        """Fallback basé sur le texte extrait"""
        text = extracted_text.lower()
        literary_keywords = ['english', 'français', 'histoire', 'philosophie', 'langues', 'rédaction', 'texte']
        scientific_keywords = ['math', 'physique', 'chimie', 'svt', 'informatique', 'économie', 'equation', 'calcul']
        
        if any(keyword in text for keyword in literary_keywords):
            return {
                'branch': 'Littéraire',
                'detected_domain': 'Langues étrangères' if 'english' in text else 'Français',
                'explanation': f"Détection basée sur le texte extrait : mots-clés littéraires détectés ({'english' if 'english' in text else 'français'})."
            }
        elif any(keyword in text for keyword in scientific_keywords):
            return {
                'branch': 'Scientifique',
                'detected_domain': 'Mathématiques' if 'math' in text else 'Physique-Chimie',
                'explanation': f"Détection basée sur le texte extrait : mots-clés scientifiques détectés ({'math' if 'math' in text else 'physique'})."
            }
        return {
            'branch': 'Général',
            'detected_domain': 'Général',
            'explanation': 'Aucun mot-clé spécifique détecté dans le texte extrait.'
        }

    def _analyze_content_type_with_education(self, domaine, type_exercice, attente, niveau):
        """Analyse avec détection Fair Use éducatif"""
        is_educational = niveau in self.EDUCATIONAL_LEVELS
        is_literary_sensitive = (domaine in self.LITERARY_DOMAINS and type_exercice in self.SENSITIVE_TYPES)
        
        if domaine in self.SCIENTIFIC_DOMAINS or type_exercice in ['QCM', 'Problème à résoudre', 'Démonstration / raisonnement']:
            return {
                'type': 'SCIENTIFIC',
                'needs_latex': True,
                'safety_level': 'LOW',
                'temperature': 0.2,
                'educational_mode': is_educational
            }
        
        if is_literary_sensitive and is_educational:
            return {
                'type': 'LITERARY_EDUCATIONAL',
                'needs_latex': False,
                'safety_level': 'EDUCATIONAL',
                'temperature': 0.7,
                'educational_mode': True,
                'fair_use': True
            }
        
        if is_literary_sensitive:
            return {
                'type': 'LITERARY_SENSITIVE',
                'needs_latex': False,
                'safety_level': 'HIGH',
                'temperature': 0.8,
                'educational_mode': False
            }
        
        if domaine in self.LITERARY_DOMAINS:
            return {
                'type': 'LITERARY_MODERATE',
                'needs_latex': False,
                'safety_level': 'MEDIUM',
                'temperature': 0.6,
                'educational_mode': is_educational
            }
        
        return {
            'type': 'GENERAL',
            'needs_latex': False,
            'safety_level': 'MEDIUM',
            'temperature': 0.5,
            'educational_mode': is_educational
        }

    def _educational_fallback(self, domaine, type_exercice, niveau, analysis):
        """Fallback pédagogique si copyright bloqué"""
        logger.info("Mode fallback éducatif activé")
        return {
            'success': True,
            'educational_mode': True,
            'extracted_text': f"Méthode pédagogique générale - {domaine} {niveau}",
            'result': f"Résultat Final: Méthode d'analyse structurée pour {type_exercice}",
            'steps': [
                f"CONTEXTE PÉDAGOGIQUE {niveau}: ",
                "1. Méthode générale d'analyse adaptée au niveau",
                "2. Structure recommandée pour ce type d'exercice",
                "3. Conseils méthodologiques pour réussir",
                "4. Exemple générique d'application",
                "5. Points d'amélioration pour l'élève"
            ]
        }

    def call_gemini_api(self, image_bytes, domaine, niveau, type_exercice, attente, infos, content_analysis):
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        safety_settings = self._get_educational_safety_settings(content_analysis)
        prompt = self._build_educational_prompt(content_analysis, domaine, niveau, type_exercice, attente, infos)

        try:
            image_part = {'mime_type': 'image/jpeg', 'data': image_bytes}
            
            response = model.generate_content(
                [prompt, image_part],
                safety_settings=safety_settings,
                generation_config={
                    "temperature": content_analysis['temperature'],
                    "top_p": 0.9,
                    "max_output_tokens": 5000
                }
            )

            candidate = response.candidates[0]
            
            if candidate.finish_reason == 4:  # COPYRIGHT_BLOCK
                logger.warning(f"Copyright éducatif bloqué: {content_analysis['type']}")
                return {
                    'success': False,
                    'message': 'Contenu sensible détecté. Mode pédagogique activé.',
                    'error_type': 'COPYRIGHT_BLOCK'
                }

            if candidate.finish_reason != 1 or not candidate.content.parts:
                return {
                    'success': False,
                    'message': 'Réponse invalide.',
                    'error_type': 'INVALID_RESPONSE'
                }

            content = response.text
            logger.info(f"Mode: {content_analysis.get('educational_mode', False)} | Réponse: {content[:150]}...")

            return self._parse_gemini_response(content, content_analysis['needs_latex'])

        except Exception as e:
            logger.error(f"Erreur Gemini: {str(e)}")
            return {'success': False, 'message': f'Erreur API: {str(e)}', 'error_type': 'API_ERROR'}

    def _get_educational_safety_settings(self, analysis):
        """Safety settings avec exception éducative"""
        base_settings = [
            {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
            {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE}
        ]
        
        safety_level = analysis['safety_level']
        
        if safety_level == 'EDUCATIONAL':
            base_settings.extend([
                {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
                {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_LOW_AND_ABOVE}
            ])
        elif safety_level == 'HIGH':
            base_settings.append({"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE})
        else:
            base_settings.append({"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH})
        
        return base_settings

    def _build_educational_prompt(self, analysis, domaine, niveau, type_exercice, attente, infos):
        """Prompt avec contexte éducatif Fair Use"""
        educational_mode = analysis.get('educational_mode', False)
        type_content = analysis['type']
        
        if type_content == 'SCIENTIFIC':
            return self._build_scientific_prompt(niveau, type_exercice, attente, analysis['needs_latex'])
        
        elif type_content == 'LITERARY_EDUCATIONAL':
            return self._build_educational_literary_prompt(niveau, type_exercice, attente, domaine)
        
        elif type_content == 'LITERARY_SENSITIVE':
            return self._build_literary_sensitive_prompt(niveau, type_exercice, attente)
        
        elif type_content == 'LITERARY_MODERATE':
            if educational_mode:
                return self._build_educational_literary_prompt(niveau, type_exercice, attente, domaine)
            return self._build_literary_moderate_prompt(niveau, type_exercice, attente)
        
        else:
            return self._build_general_prompt(niveau, type_exercice, attente)

    def _build_educational_literary_prompt(self, niveau, type_exercice, attente, domaine):
        """Prompt PROFESSEUR pour contenu littéraire éducatif — même structure JSON que scientifique"""
        return f"""
Assistant professeur certifié en {domaine} — niveau {niveau}
Type d'exercice : {type_exercice} | Attente : {attente}

🎓 Objectif :
Corriger l'exercice de façon pédagogique et méthodique, en respectant le cadre du fair use éducatif :
- Citations courtes (max 150 mots)
- Pas de reproduction intégrale d'œuvres
- Explication méthodologique et critique
- Correction structurée et compréhensible pour l'élève

📋 Instructions :
1. Extraire le texte de l'image (reformulé si nécessaire)
2. Fournir une correction complète et pédagogique
3. Structurer la réponse sous forme de JSON au format suivant :

JSON :
{{
  "extracted_text": "Texte avec LaTeX si équations",
  "result": "Résultat Final : correction de l'exercice ",
  "steps": ["Correction Détaillées : ", "1. Analyse", "$$calculs$$", "2. Résolution"]
}}

⚠️ IMPORTANT :
- Réponds uniquement avec le JSON valide ci-dessus.
- N’ajoute aucun texte hors du JSON.
"""




    def _build_scientific_prompt(self, niveau, type_exercice, attente, needs_latex):
        latex_instruction = "Utilisez LaTeX $$pour équations$$ et $inline$." if needs_latex else ""
        return f"""
Assistant scientifique expert niveau {niveau}
Type: {type_exercice} | Attente: {attente}

1. Extrayez texte image avec {latex_instruction}
2. Solution détaillée avec calculs LaTeX
3. Résultat final clair

JSON :
{{
  "extracted_text": "Texte avec LaTeX si équations",
  "result": "Résultat Final : réponse concise",
  "steps": ["Correction Détaillées : ", "1. Analyse", "$$calculs$$", "2. Résolution"]
}}
        """

    def _build_literary_sensitive_prompt(self, niveau, type_exercice, attente):
        return f"""
⚠️ CRÉATION 100% ORIGINALE - AUCUN COPYRIGHT ⚠️
Niveau {niveau} | Type: {type_exercice}

1. Reformulez AVEC VOS MOTS
2. Méthode originale d'analyse
3. Exemples FICTIFS

JSON :
{{
  "extracted_text": "Reformulation originale",
  "result": "Méthode originale",
  "steps": ["Étapes originales", "Exemple fictif"]
}}
        """

    def _build_literary_moderate_prompt(self, niveau, type_exercice, attente):
        return f"""
Assistant {niveau} - {type_exercice}
Créez contenu original :
1. Reformulation
2. Analyse originale
3. Exemples génériques

JSON :
{{
  "extracted_text": "Reformulation",
  "result": "Analyse concise",
  "steps": ["1. Méthode", "2. Exemple générique"]
}}
        """

    def _build_general_prompt(self, niveau, type_exercice, attente):
        return f"""
Assistant {niveau} - {type_exercice}
Solution originale.

JSON :
{{
  "extracted_text": "Texte extrait",
  "result": "Résultat final ou correction de l'exercice",
  "steps": ["Étapes"]
}}
        """

   # ← CORRECTION : parsing plus robuste
    def _parse_gemini_response(self, content, needs_latex):
        """Parse robuste avec fallback en cas de JSON incomplet."""
        try:
            result = json.loads(content.strip())
        except json.JSONDecodeError:
            # Tentative de récupération du bloc JSON brut
            try:
                start = content.find('{')
                end = content.rfind('}') + 1
                if start != -1 and end > start:
                    result = json.loads(content[start:end])
                else:
                    raise
            except Exception:
                # Fallback ultime
                return {
                    'success': True,
                    'extracted_text': content[:500],
                    'result': 'Réponse partielle analysée',
                    'steps': [content[:1000]]
                }

        # Nettoyage LaTeX pour les domaines non-scientifiques
        if not needs_latex:
            result['result'] = result.get('result', '').replace('$\\text{', '').replace('}$', '')
            result['steps'] = [
                step.replace('$\\text{', '').replace('}$', '')
                for step in result.get('steps', [])
            ]

        return {
            'success': True,
            'extracted_text': result.get('extracted_text', content[:500]),
            'result': result.get('result', ''),
            'steps': result.get('steps', [])
        }


class HistoryView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        corrections = CorrectionHistory.objects.filter(user=request.user).order_by('-created_at')
        serializer = CorrectionHistorySerializer(corrections, many=True)
        return Response(serializer.data)



@api_view(['GET'])
def user_stats(request):
    from django.db.models import Count
    permission_classes = [IsAuthenticated]
    image_corrections = CorrectionHistory.objects.filter(
        user=request.user
    ).count()
    
    # Chat questions (si tu as déjà des UsageLog)
    chat_questions = UsageLog.objects.filter(
        subscription__user=request.user,
        action='CHAT_QUESTION'
    ).count()

    return Response({
        'success': True,
        'data': {
            'used_image_corrections': image_corrections,
            'used_chat_questions': chat_questions,
        }
    })


# backend/views.py
import google.generativeai as genai
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import ChatSession, ChatMessage
from .serializers import (
    ChatSessionListSerializer, ChatSessionDetailSerializer, ChatMessageSerializer
)

genai.configure(api_key=settings.GEMINI_API_KEY)

class ChatSessionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChatSessionListSerializer

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user, is_active=True)

    def perform_create(self, serializer):
        # Créer avec titre générique
        session = serializer.save(user=self.request.user)
        # Premier message IA
        ChatMessage.objects.create(
            session=session,
            role='assistant',
            content="Bonjour ! Posez-moi une question sur vos devoirs."
        )

class ChatSessionDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChatSessionDetailSerializer

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user, is_active=True)
    
    
# views.py → ChatMessageCreateView (VERSION MÉMOIRE ACTIVE)
class ChatMessageCreateView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChatMessageSerializer

    def create(self, request, *args, **kwargs):
        user = request.user
        session_id = request.data.get('session_id')
        user_message = request.data.get('content', '').strip()

        if not user_message:
            return Response({
                'success': False,
                'message': 'Contenu du message requis.'
            }, status=400)

        # === CRÉER SESSION SI ABSENTE ===
        if not session_id:
            session = ChatSession.objects.create(
                user=user,
                title="Nouvelle discussion"
            )
            # Message d'accueil
            ChatMessage.objects.create(
                session=session,
                role='model',
                content="Bonjour ! Posez-moi une question sur vos devoirs."
            )
        else:
            try:
                session = ChatSession.objects.get(id=session_id, user=user, is_active=True)
            except ChatSession.DoesNotExist:
                return Response({'success': False, 'message': 'Session introuvable.'}, status=404)

        # === VÉRIFIER QUOTA ===
        try:
            subscription = Subscription.objects.get(user=user, is_active=True)
            if subscription.chat_questions_remaining <= 0:
                return Response({
                    'success': False,
                    'message': 'Quota de questions épuisé. Passez à un pack supérieur.',
                    'upgrade_required': True
                }, status=403)
        except Subscription.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Aucun abonnement actif.'
            }, status=403)

        # === SAUVEGARDER MESSAGE UTILISATEUR ===
        user_msg = ChatMessage.objects.create(
            session=session,
            role='user',
            content=user_message
        )

        # === APPEL GEMINI AVEC MÉMOIRE (LE COEUR DU CHATBOT) ===
        model = genai.GenerativeModel('gemini-2.5-flash')  # Plus rapide & meilleur contexte

        # Récupère TOUT l'historique
        history = session.messages.all().order_by('created_at')
        chat_history = []
        for msg in history:
            role = "user" if msg.role == 'user' else "model"
            chat_history.append({"role": role, "parts": [msg.content]})

        # Démarre le chat avec mémoire
        chat = model.start_chat(history=chat_history)

        # Envoie SEULEMENT le nouveau message
        try:
            start_time = timezone.now()
            response = chat.send_message(user_message)
            response_time = (timezone.now() - start_time).total_seconds() * 1000

            # Sauvegarde réponse IA
            ai_msg = ChatMessage.objects.create(
                session=session,
                role='model',
                content=response.text,
                gemini_response_time=round(response_time, 2)
            )

            # Déduit quota
            subscription.chat_questions_remaining -= 1
            subscription.save()

            # TITRE PRO PAR GEMINI
            if session.messages.filter(role='user').count() == 1:
                title_prompt = f"""
                Tu es un expert en titres accrocheurs.
                Voici le premier message de l'utilisateur : "{user_message}"
                
                Génère UN SEUL titre court (5-8 mots max), professionnel et pédagogique.
                Exemples :
                - "Racine carrée expliquée simplement"
                - "Adverbes : 3 exemples clés"
                - "Participe passé : règle facile"
                
                Réponds UNIQUEMENT le titre, rien d'autre.
                """
                
                try:
                    title_response = model.generate_content(title_prompt)
                    suggested_title = title_response.text.strip()
                    
                    if len(suggested_title) > 60:
                        suggested_title = suggested_title[:57] + "..."
                        
                    session.title = suggested_title
                    session.save()
                    logger.info(f"Titre IA généré : {suggested_title}")
                    
                except Exception as e:
                    logger.warning(f"Échec titre IA : {e}")
                    fallback = user_message[:47] + ("..." if len(user_message) > 50 else "")
                    session.title = fallback
                    session.save()

            return Response({
                'success': True,
                'message': 'Réponse générée',
                'data': ChatMessageSerializer(ai_msg).data,
                'remaining_questions': subscription.chat_questions_remaining,
                'session_id': str(session.id)
            })

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Erreur IA : {str(e)}'
            }, status=500)





# views.py
import os
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import google.generativeai as genai
import base64

# treatment/views.py
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_local_and_save(request):
    filename = request.data.get('filename')
    if not filename:
        return Response({'success': False, 'message': 'filename requis'}, status=400)

    # === CHEMIN LOCAL ===
    file_path = os.path.join(settings.BASE_DIR, 'treatment', 'media', 'images', filename)
    if not os.path.exists(file_path):
        return Response({'success': False, 'message': f'Image non trouvée : {filename}'}, status=404)

    # === CONTEXTE ===
    domaine = request.data.get('domaine', 'Mathématiques')
    niveau = request.data.get('niveau', 'Collège')
    type_ex = request.data.get('type_exercice', 'Problème')
    attente = request.data.get('attente', 'Étape par étape')
    infos = request.data.get('infos', '')

    # === SAUVEGARDE DANS LA BASE (même sans upload) ===
    # On copie l'image dans media/corrections/ pour l'historique
    from django.core.files import File
    import shutil
    from datetime import datetime

    # Crée le dossier si besoin
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'corrections', datetime.now().strftime('%Y/%m/%d'))
    os.makedirs(upload_dir, exist_ok=True)

    # Copie le fichier
    new_filename = f"{request.user.id}_{int(datetime.now().timestamp())}_{filename}"
    destination_path = os.path.join(upload_dir, new_filename)
    shutil.copy(file_path, destination_path)

    # Sauvegarde en base
    correction = ImageCorrection.objects.create(
        user=request.user,
        domaine=domaine,
        niveau=niveau,
        type_exercice=type_ex,
        attente=attente,
        infos_complementaires=infos,
        correction_text="Analyse en cours...",
    )
    # Associe l'image
    with open(destination_path, 'rb') as f:
        correction.image.save(new_filename, File(f), save=True)

    # === GEMINI VISION ===
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')

    with open(file_path, "rb") as img_file:
        image_bytes = img_file.read()

    # === CORRECT MIME TYPE ===
    ext = filename.split('.')[-1].lower()
    mime_type = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp',
        'gif': 'image/gif',
    }.get(ext, 'image/jpeg')

    image_part = {
        "mime_type": mime_type,
        "data": base64.b64encode(image_bytes).decode('utf-8')
    }
    
    prompt = f"""
    CORRIGE CET EXERCICE PHOTO
    Matière : {domaine}
    Niveau : {niveau}
    Type : {type_ex}
    Attente : {attente}
    Infos : {infos}

    Réponds en Markdown avec :
    - Question reconnue
    - Correction détaillée
    - Réponse finale en cadre
    """

    try:
        response = model.generate_content([prompt, image_part])
        correction.correction_text = response.text
        correction.save()

        return Response({
            'success': True,
            'correction_id': correction.id,
            'filename': filename,
            'correction': response.text,
            'image_url': correction.image.url,
            'saved_at': correction.created_at.isoformat()
        })

    except Exception as e:
        correction.correction_text = f"Erreur Gemini : {str(e)}"
        correction.save()
        return Response({'success': False, 'error': str(e)}, status=500)
    





# treatment/views.py
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def correct_and_upload(request):
    image_file = request.FILES.get('image')
    if not image_file:
        return Response({'success': False, 'message': 'Image requise'}, status=400)

    # === CONTEXTE ===
    domaine = request.data.get('domaine', 'Mathématiques')
    niveau = request.data.get('niveau', 'Collège')
    type_ex = request.data.get('type_exercice', 'Problème')
    attente = request.data.get('attente', 'Étape par étape')
    infos = request.data.get('infos', '')

    # === SAUVEGARDE IMMÉDIATE ===
    correction = ImageCorrection.objects.create(
        user=request.user,
        domaine=domaine,
        niveau=niveau,
        type_exercice=type_ex,
        attente=attente,
        infos_complementaires=infos,
        correction_text="Analyse en cours...",
        image=image_file,  # ← DIRECTEMENT !
    )

    # === GEMINI VISION ===
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    image_file.seek(0)  # ← REWINDE LE FICHIER
    image_bytes = image_file.read()
    ext = image_file.name.split('.')[-1].lower() if '.' in image_file.name else 'jpeg'
    mime_type = {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
        'png': 'image/png', 'webp': 'image/webp', 'gif': 'image/gif'
    }.get(ext, 'image/jpeg')

    image_part = {
        "mime_type": mime_type,
        "data": base64.b64encode(image_bytes).decode('utf-8')
    }

    prompt = f"""
Tu es une intelligence artificielle experte en éducation, chargée de corriger des exercices à partir d’une photo.  
Ta mission : fournir une réponse claire, structurée et agréable à lire sur mobile.

Voici le contexte :
- Matière : {domaine}
- Niveau : {niveau}
- Type : {type_ex}
- Attente : {attente}
- Infos supplémentaires : {infos}

Réponds uniquement en **Markdown lisible et esthétique**, dans le style de l’application mobile ChatGPT.

Structure attendue :
1. **Question reconnue** (si identifiable)
2. **Correction détaillée**, étape par étape ou par paragraphe clair
3. **Traite l'exercice **, bien intégrée au texte (pas de cadre obligatoire)

Règles de style Markdown :
- Utilise des titres (`##`, `###`) seulement si c’est utile.
- Mets les mots importants en **gras**.
- Utilise des listes à puces ou numérotées pour les étapes.
- Utilise des blocs de code (```langage) pour les formules, calculs, ou extraits de texte.
- Un seul saut de ligne entre les paragraphes (évite les grands espaces).
- Pas de phrases inutiles comme “Voici la correction” ou “Bien sûr !”.
- Ton : clair, pédagogique, fluide — comme une vraie explication naturelle.

⚠️ Ne renvoie que du Markdown, sans HTML ni balises JSON.
"""

    try:
        response = model.generate_content([prompt, image_part])
        correction.correction_text = response.text
        correction.save()

        return Response({
            'success': True,
            'correction_id': correction.id,
            'correction': response.text,
            'image_url': correction.image.url,
            'saved_at': correction.created_at.isoformat()
        })

    except Exception as e:
        correction.correction_text = f"Erreur Gemini : {str(e)}"
        correction.save()
        return Response({'success': False, 'error': str(e)}, status=500)



# === HISTORIQUE DES CORRECTIONS PHOTO ===
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def history_corrections(request):
    corrections = ImageCorrection.objects.filter(user=request.user).order_by('-created_at')
    data = []
    for c in corrections:
        data.append({
            'id': c.id,
            'domaine': c.domaine,
            'niveau': c.niveau,
            'type_exercice': c.type_exercice,
            'attente': c.attente,
            'infos': c.infos_complementaires,
            'correction': c.correction_text,
            'image_url': request.build_absolute_uri(c.image.url),
            'date': c.created_at.strftime("%d/%m/%Y %H:%M"),
        })
    
    return Response({
        'success': True,
        'total': corrections.count(),
        'history': data
    })



    
    
# import logging
# import google.generativeai as genai
# from django.conf import settings
# import json
# from rest_framework.views import APIView
# from rest_framework.parsers import MultiPartParser, FormParser
# from rest_framework import status
# from rest_framework.response import Response
# from google.generativeai.types import HarmCategory, HarmBlockThreshold
# from datetime import datetime
# from rest_framework.permissions import IsAuthenticated
# from .models import CorrectionHistory  # Import du modèle
# from .serializers import CorrectionHistorySerializer

# logger = logging.getLogger(__name__)
# genai.configure(api_key=settings.GEMINI_API_KEY)

# class ProcessImageView(APIView):
#     parser_classes = [MultiPartParser, FormParser]
#     permission_classes = [IsAuthenticated]

#     LITERARY_DOMAINS = [
#         'Français', 'Histoire-Géographie', 'Philosophie', 
#         'Langues étrangères', 'Autre'
#     ]
    
#     SENSITIVE_TYPES = [
#         'Exercice de rédaction', 'Analyse de texte'
#     ]
    
#     SCIENTIFIC_DOMAINS = [
#         'Mathématiques', 'Physique-Chimie', 'SVT', 
#         'Informatique', 'Économie / SES'
#     ]

#     EDUCATIONAL_LEVELS = [
#         'Lycée – Terminale', 'Lycée – Première', 'Lycée – Seconde',
#         'Collège (6ᵉ – 3ᵉ)', 'Supérieur – BTS / DUT', 'Supérieur – Licence'
#     ]

#     def post(self, request):
#         TEST_MODE = False
#         if TEST_MODE:
#             image_path = r'C:\git_project\CORRECTION APP BACKEND\treatment\images\testfr.png'
#             context_str = json.dumps({
#                 'domaine': 'Francais',
#                 'niveau': 'Lycée – Terminale',
#                 'type_exercice': 'Problème à résoudre',
#                 'attente': 'Solution étape par étape',
#                 'infos': ''
#             })
#             try:
#                 with open(image_path, 'rb') as f:
#                     image_bytes = f.read()
#             except FileNotFoundError:
#                 logger.error(f"Image locale non trouvée: {image_path}")
#                 return Response(
#                     {'success': False, 'message': f'Image locale non trouvée: {image_path}'},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
#         else:
#             image = request.FILES.get('image')
#             context_str = request.POST.get('context')

#             if not image:
#                 return Response(
#                     {'success': False, 'message': 'Aucune image fournie.'},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
#             image_bytes = image.read()

#         try:
#             context = json.loads(context_str) if context_str else {}
#             domaine = context.get('domaine', 'Mathématiques')
#             niveau = context.get('niveau', 'Collège (6ᵉ – 3ᵉ)')
#             type_exercice = context.get('type_exercice', 'Problème à résoudre')
#             attente = context.get('attente', 'Solution étape par étape')
#             infos = context.get('infos', '')
            
#             logger.info(f"Contexte: Domaine={domaine}, Type={type_exercice}, Niveau={niveau}")

#             # ✅ EXTRACTION INITIALE DU TEXTE POUR FALLBACK
#             extracted_text = self._extract_text(image_bytes)
            
#             # ✅ ANALYSE INITIALE DE LA BRANCHE PAR L'IA
#             branch_analysis = self._detect_branch(image_bytes, extracted_text)
            
#             # ✅ VÉRIFICATION DE L'INCOHÉRENCE DOMAINE/BRANCHE
#             detected_branch = branch_analysis['branch']
#             detected_domain = branch_analysis['detected_domain']
#             domain_mismatch = None
#             if domaine != detected_domain:
#                 domain_mismatch = f"L'utilisateur a indiqué '{domaine}', mais l'exercice est détecté comme '{detected_domain}' ({detected_branch})."

#             # ✅ ANALYSE DU TYPE DE CONTENU
#             content_analysis = self._analyze_content_type_with_education(
#                 detected_domain, type_exercice, attente, niveau
#             )
            
#             ia_response = self.call_gemini_api(
#                 image_bytes, detected_domain, niveau, type_exercice, 
#                 attente, infos, content_analysis
#             )

#             # ✅ AJOUT DATE/HEURE BACKEND
#             current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

#             # Préparer la réponse JSON
#             response_data = {
#                 'success': True,
#                 'data': {
#                     'user_domain': domaine,
#                     'user_level': niveau,
#                     'user_exercise_type': type_exercice,
#                     'user_expectation': attente,
#                     'user_info': infos,
#                     'detected_branch': detected_branch,
#                     'detected_branch_explanation': branch_analysis['explanation'],
#                     'domain_mismatch': domain_mismatch,
#                     'response_datetime': current_datetime,
#                     'extracted_text': ia_response.get('extracted_text', extracted_text),
#                     'solution': {
#                         'result': ia_response.get('result', ''),
#                         'steps': ia_response.get('steps', [])
#                     }
#                 },
#                 'content_type': content_analysis['type'],
#                 'educational_mode': content_analysis.get('educational_mode', False)
#             }

#             if not ia_response.get('success', True):
#                 if ia_response.get('error_type') == 'COPYRIGHT_BLOCK':
#                     ia_response = self._educational_fallback(
#                         detected_domain, type_exercice, niveau, content_analysis
#                     )
                
#                 if not ia_response.get('success', True):
#                     response_data = {
#                         'success': False,
#                         'message': ia_response['message'],
#                         'data': {
#                             'user_domain': domaine,
#                             'user_level': niveau,
#                             'user_exercise_type': type_exercice,
#                             'user_expectation': attente,
#                             'user_info': infos,
#                             'solution': None,
#                             'detected_branch': detected_branch,
#                             'detected_branch_explanation': branch_analysis['explanation'],
#                             'domain_mismatch': domain_mismatch
#                         },
#                         'content_type': content_analysis['type'],
#                         'detected_branch': detected_branch,
#                         'detected_branch_explanation': branch_analysis['explanation']
#                     }

#             # ✅ SAUVEGARDE DANS L'HISTORIQUE
#             CorrectionHistory.objects.create(
#                 user=request.user,
#                 user_domain=domaine,
#                 user_level=niveau,
#                 user_exercise_type=type_exercice,
#                 user_expectation=attente,
#                 user_info=infos,
#                 detected_branch=detected_branch,
#                 detected_branch_explanation=branch_analysis['explanation'],
#                 domain_mismatch=domain_mismatch,
#                 response_datetime=current_datetime,
#                 extracted_text=response_data['data']['extracted_text'],
#                 solution=response_data['data']['solution'],
#                 content_type=content_analysis['type'],
#                 educational_mode=content_analysis.get('educational_mode', False),
#                 success=response_data['success'],
#                 error_message=response_data.get('message', None)
#             )

#             return Response(response_data)

#         except json.JSONDecodeError:
#             response_data = {
#                 'success': False,
#                 'message': 'Contexte invalide.',
#                 'data': {
#                     'user_domain': domaine,
#                     'user_level': niveau,
#                     'user_exercise_type': type_exercice,
#                     'user_expectation': attente,
#                     'user_info': infos
#                 }
#             }
#             # ✅ SAUVEGARDE DANS L'HISTORIQUE (ERREUR)
#             CorrectionHistory.objects.create(
#                 user=request.user,
#                 user_domain=domaine,
#                 user_level=niveau,
#                 user_exercise_type=type_exercice,
#                 user_expectation=attente,
#                 user_info=infos,
#                 success=False,
#                 error_message='Contexte invalide.'
#             )
#             return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             logger.error(f"Erreur: {str(e)}")
#             response_data = {
#                 'success': False,
#                 'message': f'Erreur serveur: {str(e)}',
#                 'data': {
#                     'user_domain': domaine,
#                     'user_level': niveau,
#                     'user_exercise_type': type_exercice,
#                     'user_expectation': attente,
#                     'user_info': infos
#                 }
#             }
#             # ✅ SAUVEGARDE DANS L'HISTORIQUE (ERREUR)
#             CorrectionHistory.objects.create(
#                 user=request.user,
#                 user_domain=domaine,
#                 user_level=niveau,
#                 user_exercise_type=type_exercice,
#                 user_expectation=attente,
#                 user_info=infos,
#                 success=False,
#                 error_message=f'Erreur serveur: {str(e)}'
#             )
#             return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def _extract_text(self, image_bytes):
#         """Extrait le texte de l'image pour fallback"""
#         try:
#             model = genai.GenerativeModel('gemini-2.5-flash')
#             image_part = {'mime_type': 'image/jpeg', 'data': image_bytes}
#             prompt = "Extrayez le texte brut de l'image sans interprétation."
#             response = model.generate_content([prompt, image_part], generation_config={"temperature": 0.1})
#             return response.text.strip()[:500]  # Limite pour éviter surcharge
#         except Exception as e:
#             logger.error(f"Erreur extraction texte: {str(e)}")
#             return ""

#     def _detect_branch(self, image_bytes, extracted_text):
#         """Analyse l'image et le texte extrait pour détecter la branche"""
#         model = genai.GenerativeModel('gemini-2.5-flash')
#         try:
#             image_part = {'mime_type': 'image/jpeg', 'data': image_bytes}
#             prompt = f"""
# Analyse l'image et le texte suivant pour déterminer si l'exercice est SCIENTIFIQUE (Mathématiques, Physique-Chimie, SVT, Informatique, Économie/SES) ou LITTÉRAIRE (Français, Histoire-Géographie, Philosophie, Langues étrangères, Autre).
# Texte extrait : {extracted_text[:500]}
# Retourne un JSON avec :
# - "branch": "Scientifique" ou "Littéraire"
# - "detected_domain": Le domaine spécifique (ex. "Anglais", "Mathématiques")
# - "explanation": Une courte explication de la détection

# JSON :
# {{
#   "branch": "Scientifique ou Littéraire",
#   "detected_domain": "Domaine détecté",
#   "explanation": "Explication de la détection"
# }}
# """
#             response = model.generate_content([prompt, image_part], generation_config={"temperature": 0.2})
#             content = response.text.strip()
#             try:
#                 result = json.loads(content)
#                 return {
#                     'branch': result.get('branch', 'Général'),
#                     'detected_domain': result.get('detected_domain', 'Général'),
#                     'explanation': result.get('explanation', 'Analyse non concluante.')
#                 }
#             except json.JSONDecodeError:
#                 # Fallback : Analyse du texte extrait
#                 return self._fallback_branch_detection(extracted_text)
#         except Exception as e:
#             logger.error(f"Erreur détection branche: {str(e)}")
#             return self._fallback_branch_detection(extracted_text)

#     def _fallback_branch_detection(self, extracted_text):
#         """Fallback basé sur le texte extrait"""
#         text = extracted_text.lower()
#         literary_keywords = ['english', 'français', 'histoire', 'philosophie', 'langues', 'rédaction', 'texte']
#         scientific_keywords = ['math', 'physique', 'chimie', 'svt', 'informatique', 'économie', 'equation', 'calcul']
        
#         if any(keyword in text for keyword in literary_keywords):
#             return {
#                 'branch': 'Littéraire',
#                 'detected_domain': 'Langues étrangères' if 'english' in text else 'Français',
#                 'explanation': f"Détection basée sur le texte extrait : mots-clés littéraires détectés ({'english' if 'english' in text else 'français'})."
#             }
#         elif any(keyword in text for keyword in scientific_keywords):
#             return {
#                 'branch': 'Scientifique',
#                 'detected_domain': 'Mathématiques' if 'math' in text else 'Physique-Chimie',
#                 'explanation': f"Détection basée sur le texte extrait : mots-clés scientifiques détectés ({'math' if 'math' in text else 'physique'})."
#             }
#         return {
#             'branch': 'Général',
#             'detected_domain': 'Général',
#             'explanation': 'Aucun mot-clé spécifique détecté dans le texte extrait.'
#         }

#     def _analyze_content_type_with_education(self, domaine, type_exercice, attente, niveau):
#         """Analyse avec détection Fair Use éducatif"""
#         is_educational = niveau in self.EDUCATIONAL_LEVELS
#         is_literary_sensitive = (domaine in self.LITERARY_DOMAINS and type_exercice in self.SENSITIVE_TYPES)
        
#         if domaine in self.SCIENTIFIC_DOMAINS or type_exercice in ['QCM', 'Problème à résoudre', 'Démonstration / raisonnement']:
#             return {
#                 'type': 'SCIENTIFIC',
#                 'needs_latex': True,
#                 'safety_level': 'LOW',
#                 'temperature': 0.2,
#                 'educational_mode': is_educational
#             }
        
#         if is_literary_sensitive and is_educational:
#             return {
#                 'type': 'LITERARY_EDUCATIONAL',
#                 'needs_latex': False,
#                 'safety_level': 'EDUCATIONAL',
#                 'temperature': 0.7,
#                 'educational_mode': True,
#                 'fair_use': True
#             }
        
#         if is_literary_sensitive:
#             return {
#                 'type': 'LITERARY_SENSITIVE',
#                 'needs_latex': False,
#                 'safety_level': 'HIGH',
#                 'temperature': 0.8,
#                 'educational_mode': False
#             }
        
#         if domaine in self.LITERARY_DOMAINS:
#             return {
#                 'type': 'LITERARY_MODERATE',
#                 'needs_latex': False,
#                 'safety_level': 'MEDIUM',
#                 'temperature': 0.6,
#                 'educational_mode': is_educational
#             }
        
#         return {
#             'type': 'GENERAL',
#             'needs_latex': False,
#             'safety_level': 'MEDIUM',
#             'temperature': 0.5,
#             'educational_mode': is_educational
#         }

#     def _educational_fallback(self, domaine, type_exercice, niveau, analysis):
#         """Fallback pédagogique si copyright bloqué"""
#         logger.info("Mode fallback éducatif activé")
#         return {
#             'success': True,
#             'educational_mode': True,
#             'extracted_text': f"Méthode pédagogique générale - {domaine} {niveau}",
#             'result': f"Résultat Final: Méthode d'analyse structurée pour {type_exercice}",
#             'steps': [
#                 f"CONTEXTE PÉDAGOGIQUE {niveau}: ",
#                 "1. Méthode générale d'analyse adaptée au niveau",
#                 "2. Structure recommandée pour ce type d'exercice",
#                 "3. Conseils méthodologiques pour réussir",
#                 "4. Exemple générique d'application",
#                 "5. Points d'amélioration pour l'élève"
#             ]
#         }

#     def call_gemini_api(self, image_bytes, domaine, niveau, type_exercice, attente, infos, content_analysis):
#         model = genai.GenerativeModel('gemini-2.5-flash')
        
#         safety_settings = self._get_educational_safety_settings(content_analysis)
#         prompt = self._build_educational_prompt(content_analysis, domaine, niveau, type_exercice, attente, infos)

#         try:
#             image_part = {'mime_type': 'image/jpeg', 'data': image_bytes}
            
#             response = model.generate_content(
#                 [prompt, image_part],
#                 safety_settings=safety_settings,
#                 generation_config={
#                     "temperature": content_analysis['temperature'],
#                     "top_p": 0.9,
#                     "max_output_tokens": 5000
#                 }
#             )

#             candidate = response.candidates[0]
            
#             if candidate.finish_reason == 4:  # COPYRIGHT_BLOCK
#                 logger.warning(f"Copyright éducatif bloqué: {content_analysis['type']}")
#                 return {
#                     'success': False,
#                     'message': 'Contenu sensible détecté. Mode pédagogique activé.',
#                     'error_type': 'COPYRIGHT_BLOCK'
#                 }

#             if candidate.finish_reason != 1 or not candidate.content.parts:
#                 return {
#                     'success': False,
#                     'message': 'Réponse invalide.',
#                     'error_type': 'INVALID_RESPONSE'
#                 }

#             content = response.text
#             logger.info(f"Mode: {content_analysis.get('educational_mode', False)} | Réponse: {content[:150]}...")

#             return self._parse_gemini_response(content, content_analysis['needs_latex'])

#         except Exception as e:
#             logger.error(f"Erreur Gemini: {str(e)}")
#             return {'success': False, 'message': f'Erreur API: {str(e)}', 'error_type': 'API_ERROR'}

#     def _get_educational_safety_settings(self, analysis):
#         """Safety settings avec exception éducative"""
#         base_settings = [
#             {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
#             {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE}
#         ]
        
#         safety_level = analysis['safety_level']
        
#         if safety_level == 'EDUCATIONAL':
#             base_settings.extend([
#                 {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
#                 {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_LOW_AND_ABOVE}
#             ])
#         elif safety_level == 'HIGH':
#             base_settings.append({"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE})
#         else:
#             base_settings.append({"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH})
        
#         return base_settings

#     def _build_educational_prompt(self, analysis, domaine, niveau, type_exercice, attente, infos):
#         """Prompt avec contexte éducatif Fair Use"""
#         educational_mode = analysis.get('educational_mode', False)
#         type_content = analysis['type']
        
#         if type_content == 'SCIENTIFIC':
#             return self._build_scientific_prompt(niveau, type_exercice, attente, analysis['needs_latex'])
        
#         elif type_content == 'LITERARY_EDUCATIONAL':
#             return self._build_educational_literary_prompt(niveau, type_exercice, attente, domaine)
        
#         elif type_content == 'LITERARY_SENSITIVE':
#             return self._build_literary_sensitive_prompt(niveau, type_exercice, attente)
        
#         elif type_content == 'LITERARY_MODERATE':
#             if educational_mode:
#                 return self._build_educational_literary_prompt(niveau, type_exercice, attente, domaine)
#             return self._build_literary_moderate_prompt(niveau, type_exercice, attente)
        
#         else:
#             return self._build_general_prompt(niveau, type_exercice, attente)

#     def _build_educational_literary_prompt(self, niveau, type_exercice, attente, domaine):
#         """Prompt PROFESSEUR pour contenu littéraire éducatif — même structure JSON que scientifique"""
#         return f"""
# Assistant professeur certifié en {domaine} — niveau {niveau}
# Type d'exercice : {type_exercice} | Attente : {attente}

# 🎓 Objectif :
# Corriger l'exercice de façon pédagogique et méthodique, en respectant le cadre du fair use éducatif :
# - Citations courtes (max 150 mots)
# - Pas de reproduction intégrale d'œuvres
# - Explication méthodologique et critique
# - Correction structurée et compréhensible pour l'élève

# 📋 Instructions :
# 1. Extraire le texte de l'image (reformulé si nécessaire)
# 2. Fournir une correction complète et pédagogique
# 3. Structurer la réponse sous forme de JSON au format suivant :

# JSON :
# {{
#   "extracted_text": "Texte avec LaTeX si équations",
#   "result": "Résultat Final : réponse concise",
#   "steps": ["Correction Détaillées : ", "1. Analyse", "$$calculs$$", "2. Résolution"]
# }}

# ⚠️ IMPORTANT :
# - Réponds uniquement avec le JSON valide ci-dessus.
# - N’ajoute aucun texte hors du JSON.
# """




#     def _build_scientific_prompt(self, niveau, type_exercice, attente, needs_latex):
#         latex_instruction = "Utilisez LaTeX $$pour équations$$ et $inline$." if needs_latex else ""
#         return f"""
# Assistant scientifique expert niveau {niveau}
# Type: {type_exercice} | Attente: {attente}

# 1. Extrayez texte image avec {latex_instruction}
# 2. Solution détaillée avec calculs LaTeX
# 3. Résultat final clair

# JSON :
# {{
#   "extracted_text": "Texte avec LaTeX si équations",
#   "result": "Résultat Final : réponse concise",
#   "steps": ["Correction Détaillées : ", "1. Analyse", "$$calculs$$", "2. Résolution"]
# }}
#         """

#     def _build_literary_sensitive_prompt(self, niveau, type_exercice, attente):
#         return f"""
# ⚠️ CRÉATION 100% ORIGINALE - AUCUN COPYRIGHT ⚠️
# Niveau {niveau} | Type: {type_exercice}

# 1. Reformulez AVEC VOS MOTS
# 2. Méthode originale d'analyse
# 3. Exemples FICTIFS

# JSON :
# {{
#   "extracted_text": "Reformulation originale",
#   "result": "Méthode originale",
#   "steps": ["Étapes originales", "Exemple fictif"]
# }}
#         """

#     def _build_literary_moderate_prompt(self, niveau, type_exercice, attente):
#         return f"""
# Assistant {niveau} - {type_exercice}
# Créez contenu original :
# 1. Reformulation
# 2. Analyse originale
# 3. Exemples génériques

# JSON :
# {{
#   "extracted_text": "Reformulation",
#   "result": "Analyse concise",
#   "steps": ["1. Méthode", "2. Exemple générique"]
# }}
#         """

#     def _build_general_prompt(self, niveau, type_exercice, attente):
#         return f"""
# Assistant {niveau} - {type_exercice}
# Solution originale.

# JSON :
# {{
#   "extracted_text": "Texte extrait",
#   "result": "Résultat final",
#   "steps": ["Étapes"]
# }}
#         """

#     def _parse_gemini_response(self, content, needs_latex):
#         """Parse robuste"""
#         try:
#             result = json.loads(content.strip())
#             # Supprimer LaTeX pour les exercices littéraires
#             if not needs_latex:
#                 result['result'] = result.get('result', '').replace('$\\text{', '').replace('}$', '')
#                 result['steps'] = [step.replace('$\\text{', '').replace('}$', '') for step in result.get('steps', [])]
#             return {
#                 'success': True,
#                 'extracted_text': result.get('extracted_text', ''),
#                 'result': result.get('result', ''),
#                 'steps': result.get('steps', [])
#             }
#         except json.JSONDecodeError:
#             start, end = content.find('{'), content.rfind('}') + 1
#             if start != -1 and end > start:
#                 try:
#                     result = json.loads(content[start:end])
#                     if not needs_latex:
#                         result['result'] = result.get('result', '').replace('$\\text{', '').replace('}$', '')
#                         result['steps'] = [step.replace('$\\text{', '').replace('}$', '') for step in result.get('steps', [])]
#                     return {
#                         'success': True,
#                         'extracted_text': result.get('extracted_text', content[:200]),
#                         'result': result.get('result', ''),
#                         'steps': result.get('steps', [content[:500]])
#                     }
#                 except:
#                     pass
        
#         return {
#             'success': True,
#             'extracted_text': content[:300],
#             'result': 'Réponse analysée',
#             'steps': [content[:800]]
#         }



# class HistoryView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         corrections = CorrectionHistory.objects.filter(user=request.user).order_by('-created_at')
#         serializer = CorrectionHistorySerializer(corrections, many=True)
#         return Response(serializer.data)

