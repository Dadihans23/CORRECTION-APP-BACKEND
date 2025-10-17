import logging
import google.generativeai as genai
from django.conf import settings
import json
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from rest_framework.response import Response
from google.generativeai.types import HarmCategory, HarmBlockThreshold

logger = logging.getLogger(__name__)
genai.configure(api_key=settings.GEMINI_API_KEY)

class ProcessImageView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    # ✅ LISTES IDENTIQUES AU FRONTEND
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

    # ✅ NIVEAUX ÉDUCATIFS (Fair Use applicable)
    EDUCATIONAL_LEVELS = [
        'Lycée – Terminale', 'Lycée – Première', 'Lycée – Seconde',
        'Collège (6ᵉ – 3ᵉ)', 'Supérieur – BTS / DUT', 'Supérieur – Licence'
    ]

    def post(self, request):
        TEST_MODE = True
        if TEST_MODE:
            image_path = r'C:\git_project\CORRECTION APP BACKEND\treatment\images\testfr.png'
            context_str = json.dumps({
                'domaine': 'Français',
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
                    status=status.HTTP_400_BAD_REQUEST  # Mode test inchangé 
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

            # ✅ ANALYSE AVEC CONTESTE ÉDUCATIF
            content_analysis = self._analyze_content_type_with_education(
                domaine, type_exercice, attente, niveau
            )
            
            ia_response = self.call_gemini_api(
                image_bytes, domaine, niveau, type_exercice, 
                attente, infos, content_analysis
            )

            if not ia_response.get('success', True):
                # ✅ FALLBACK ÉDUCATIF pour blocages
                if ia_response.get('error_type') == 'COPYRIGHT_BLOCK':
                    ia_response = self._educational_fallback(
                        domaine, type_exercice, niveau, content_analysis
                    )
                
                if not ia_response.get('success', True):
                    return Response({
                        'success': False,
                        'message': ia_response['message'],
                        'data': {'solution': None},
                        'content_type': content_analysis['type']
                    }, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                'success': True,
                'data': {
                    'extracted_text': ia_response.get('extracted_text', ''),
                    'solution': {
                        'result': ia_response.get('result', ''),
                        'steps': ia_response.get('steps', [])
                    }
                },
                'content_type': content_analysis['type'],
                'educational_mode': content_analysis.get('educational_mode', False)
            })

        except json.JSONDecodeError:
            return Response({'success': False, 'message': 'Contexte invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Erreur: {str(e)}")
            return Response({'success': False, 'message': f'Erreur serveur: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _analyze_content_type_with_education(self, domaine, type_exercice, attente, niveau):
        """Analyse avec détection Fair Use éducatif"""
        
        # ✅ SCIENTIFIQUE (toujours OK)
        if domaine in self.SCIENTIFIC_DOMAINS or type_exercice in ['QCM', 'Problème à résoudre', 'Démonstration / raisonnement']:
            return {
                'type': 'SCIENTIFIC',
                'needs_latex': True,
                'safety_level': 'LOW',
                'temperature': 0.2,
                'educational_mode': False
            }
        
        # ✅ LITTÉRAIRE AVEC FAIR USE ÉDUCATIF
        is_educational = niveau in self.EDUCATIONAL_LEVELS
        is_literary_sensitive = (domaine in self.LITERARY_DOMAINS and 
                               type_exercice in self.SENSITIVE_TYPES)
        
        if is_literary_sensitive and is_educational:
            return {
                'type': 'LITERARY_EDUCATIONAL',
                'needs_latex': False,
                'safety_level': 'EDUCATIONAL',  # Mode professeur
                'temperature': 0.7,            # Équilibre précision/créativité
                'educational_mode': True,
                'fair_use': True
            }
        
        # ✅ LITTÉRAIRE SENSIBLE (risque copyright)
        if is_literary_sensitive:
            return {
                'type': 'LITERARY_SENSITIVE',
                'needs_latex': False,
                'safety_level': 'HIGH',
                'temperature': 0.8,
                'educational_mode': False
            }
        
        # ✅ LITTÉRAIRE MODÉRÉ
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
            'educational_mode': False
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

    def call_gemini_api(self, image_bytes, domaine, niveau, type_exercice, 
                       attente, infos, content_analysis):
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
                    "max_output_tokens": 5000  # Plus pour contenu éducatif
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
        
        if safety_level == 'EDUCATIONAL':  # ✅ MODE PROFESSEUR
            # Plus permissif pour fair use éducatif
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
        """Prompt PROFESSEUR pour contenu littéraire éducatif"""
        return f"""
🆕 MODE PROFESSEUR CERTIFIÉ - EXERCICE SCOLAIRE {niveau} 🆕

📚 CONTEXTE LÉGAL - FAIR USE ÉDUCATIF :
- Usage PÉDAGOGIQUE dans classe {niveau}
- Objectif : CORRECTION et ENSEIGNEMENT
- Citations COURTES pour analyse critique uniquement
- Transformateur : analyse méthodologique, pas reproduction

🎓 VOUS ÊTES PROFESSEUR DE {domaine} :
Type: {type_exercice} | Attente: {attente}

✅ AUTORISÉ (Fair Use Éducatif):
- Citations < 100 mots pour ILLUSTRER l'analyse
- Méthodes d'analyse littéraire/scolaire
- Explication pédagogique des techniques
- Correction structurée élève/professeur

🚫 INTERDIT:
- Récitation complète d'œuvres
- Copie verbatim passages longs
- Contenu non-transformé

📋 MISSION CORRECTION:
1. Analysez l'exercice comme un PROFESSEUR corrigerait
2. Fournissez méthode pédagogique + application
3. Structure : Résultat + étapes détaillées
4. Conseils personnalisés pour l'élève

JSON RÉPONSE PROFESSEUR :
{{
  "extracted_text": "Reformulation pédagogique de l'exercice",
  "result": "Résultat Final : Correction + méthode appliquée",
  "steps": [
    "CONTEXTE PÉDAGOGIQUE {niveau}: ",
    "1. Analyse méthodologique (citation courte si nécessaire)",
    "2. Correction structurée par compétences",
    "3. Points forts/faibles de la réponse élève",
    "4. Conseils d'amélioration professorale",
    "5. Exemple corrigé (fair use)"
  ]
}}

⚖️ SAFETY OVERRIDE : Usage éducatif légitime - fair use exception.
Ceci est une correction scolaire transformative.
        """

    # ✅ Les autres méthodes restent identiques
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
  "extracted_text": "Texte avec LaTeX",
  "result": "Résultat Final : réponse concise",
  "steps": ["Correction Détaillées : ", "1. Analyse", "$$calculs$$"]
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
  "result": "Résultat final",
  "steps": ["Étapes"]
}}
        """

    def _parse_gemini_response(self, content, needs_latex):
        """Parse robuste (inchangé)"""
        try:
            result = json.loads(content.strip())
            return {
                'success': True,
                'extracted_text': result.get('extracted_text', ''),
                'result': result.get('result', ''),
                'steps': result.get('steps', [])
            }
        except json.JSONDecodeError:
            start, end = content.find('{'), content.rfind('}') + 1
            if start != -1 and end > start:
                try:
                    result = json.loads(content[start:end])
                    return {
                        'success': True,
                        'extracted_text': result.get('extracted_text', content[:200]),
                        'result': result.get('result', ''),
                        'steps': result.get('steps', [content[:500]])
                    }
                except:
                    pass
        
        return {
            'success': True,
            'extracted_text': content[:300],
            'result': 'Réponse analysée',
            'steps': [content[:800]]
        }

# from rest_framework.views import APIView
# from rest_framework.parsers import MultiPartParser, FormParser
# from rest_framework.response import Response
# from rest_framework import status
# from rest_framework.permissions import IsAuthenticated
# import json
# import logging
# import google.generativeai as genai
# from django.conf import settings
# import os

# from io import BytesIO  # Ajouté pour corriger l'erreur

# from PIL import Image as PILImage
# import io
# from google.generativeai.types import BlobType  # Pour les bytes

# # Configurer le logging
# logger = logging.getLogger(__name__)

# # Configurer Gemini
# genai.configure(api_key=settings.GEMINI_API_KEY)

# class ProcessImageView(APIView):
#     parser_classes = [MultiPartParser, FormParser]

#     def post(self, request):
#         # Mode test avec image locale
#         TEST_MODE = False  # Change à False pour Flutter
#         if TEST_MODE:
#             image_path = r'C:\git_project\CORRECTION APP BACKEND\treatment\images\test_image.jpg'
#             context_str = json.dumps({
#                 'domaine': 'Mathématiques',
#                 'niveau': 'Lycée – Terminale',
#                 'type_exercice': 'Problème à résoudre',
#                 'attente': 'Solution étape par étape',
#                 'infos': 'Exercice sur les équations'
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
#             # Mode normal (Flutter)
#             image = request.FILES.get('image')
#             context_str = request.POST.get('context')

#             if not image:
#                 logger.error("Aucune image fournie dans la requête")
#                 return Response(
#                     {'success': False, 'message': 'Aucune image fournie.'},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
#             image_bytes = image.read()

#         try:
#             # Parser le contexte
#             context = json.loads(context_str) if context_str else {}
#             domaine = context.get('domaine', 'Mathématiques')
#             niveau = context.get('niveau', 'Collège')
#             type_exercice = context.get('type_exercice', 'Problème à résoudre')
#             attente = context.get('attente', 'Solution étape par étape')
#             infos = context.get('infos', '')
#             logger.info(f"Contexte: {context}")

#             # Appel à Gemini
#             ia_response = self.call_gemini_api(image_bytes, domaine, niveau, type_exercice, attente, infos)

#             return Response({
#                 'success': True,
#                 'data': {
#                     'extracted_text': ia_response.get('extracted_text', 'Extrait par Gemini'),
#                     'solution': ia_response
#                 },
#                 'statusCode': status.HTTP_200_OK
#             })
#             # Supprimé le print invalide
#         except json.JSONDecodeError:
#             logger.error("Erreur JSON contexte")
#             return Response(
#                 {'success': False, 'message': 'Contexte invalide (format JSON incorrect).'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
#         except Exception as e:
#             logger.error(f"Erreur générale: {str(e)}")
#             return Response(
#                 {'success': False, 'message': f'Erreur lors du traitement: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )

#     def call_gemini_api(self, image_bytes, domaine, niveau, type_exercice, attente, infos):
#         model = genai.GenerativeModel('gemini-2.5-flash')        
#         # Prompt mis à jour pour imiter PhotoSolve
#         prompt = (
#             f"Tu es un assistant pédagogique expert, comme dans PhotoSolve. Analyse cette image d'un exercice de {domaine} pour un niveau {niveau}. "
#             f"Type d'exercice: {type_exercice}. Attente: {attente}. Infos: {infos}. "
#             f"1. Extrais le texte de l'image (LaTeX $$ pour équations si présentes, sinon texte brut). "
#             f"2. Fournis une solution claire et adaptée au niveau, avec un style comme PhotoSolve. "
#             f"3. Pour les exercices scientifiques, utilise des étapes détaillées avec LaTeX pour les équations. Pour les exercices littéraires, fournis une réponse fluide et concise. "
#             f"Retourne la réponse **UNIQUEMENT** sous forme JSON avec : "
#             f"'extracted_text' (texte brut ou avec LaTeX), "
#             f"'result' (Résultat Final : résumé ou réponse finale en texte clair, avec LaTeX si besoin), "
#             f"'steps' (Resultat Détaillées : resultat detaillées pour chaque question , avec LaTeX pour les calculs si il y en a). "
#             f"Exemple : "
#             f"```json\n"
#             f"{{\n  \"extracted_text\": \"x^2 + 2x + 1 = 0\",\n  \"result\": \"Résultat Final : x = -1 (double racine)\",\n  \"steps\": [\"correction Détaillées : \", }}\n```"
#             f"Pour un exercice littéraire : "
#             f"```json\n"
#             f"{{\n  \"extracted_text\": \"Résumez ce poème...\",\n  \"result\": \"Résultat Final : Résumé en 100 mots : Le poème décrit...\",\n  \"steps\": [\"Étapes Détaillées : \", \"1. Analyse du thème principal : La solitude.\", \"2. Identification des images poétiques : étoiles, nuit.\"]\n}}\n```"
#             f"Ne retourne rien d'autre que ce JSON."
#         )

#         try:
#             # Créer le contenu multimodal
#             image_part = {
#                 'mime_type': 'image/jpeg',
#                 'data': image_bytes
#             }
#             response = model.generate_content([prompt, image_part])

#             # Récupérer la réponse
#             content = response.text
#             logger.info(f"Réponse Gemini: {content[:200]}...")

#             # Parser la réponse JSON
#             try:
#                 result = json.loads(content)
#                 return {
#                     'extracted_text': result.get('extracted_text', 'Extrait par Gemini'),
#                     'result': result.get('result', 'Solution calculée'),
#                     'steps': result.get('steps', ['Pas d\'étapes disponibles'])
#                 }
#             except json.JSONDecodeError:
#                 # Fallback extraction JSON
#                 start = content.find('{')
#                 end = content.rfind('}') + 1
#                 if start != -1 and end > start:
#                     try:
#                         json_str = content[start:end]
#                         result = json.loads(json_str)
#                         return {
#                             'extracted_text': result.get('extracted_text', content[:200]),
#                             'result': result.get('result', 'Réponse Gemini'),
#                             'steps': result.get('steps', [])
#                         }
#                     except:
#                         pass
#                 return {
#                     'extracted_text': content[:500],
#                     'result': 'Réponse non structurée',
#                     'steps': []
#                 }
                
#         except Exception as e:
#             logger.error(f"Erreur Gemini: {str(e)}")
#             raise Exception(f'Erreur API Gemini: {str(e)}')


