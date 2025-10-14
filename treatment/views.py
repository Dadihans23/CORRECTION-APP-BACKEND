from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import json
import logging
import google.generativeai as genai
from django.conf import settings
import os

from io import BytesIO  # Ajouté pour corriger l'erreur

# Configurer le logging
logger = logging.getLogger(__name__)

# Configurer Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)

class ProcessImageView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        # Mode test avec image locale
        TEST_MODE = True  # Change à False pour Flutter
        if TEST_MODE:
            image_path = r'C:\git_project\CORRECTION APP BACKEND\treatment\images\test_image.jpg'
            context_str = json.dumps({
                'domaine': 'Mathématiques',
                'niveau': 'Lycée – Terminale',
                'type_exercice': 'Problème à résoudre',
                'attente': 'Solution étape par étape',
                'infos': 'Exercice sur les équations'
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
            # Mode normal (Flutter)
            image = request.FILES.get('image')
            context_str = request.POST.get('context')

            if not image:
                logger.error("Aucune image fournie dans la requête")
                return Response(
                    {'success': False, 'message': 'Aucune image fournie.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            image_bytes = image.read()

        try:
            # Parser le contexte
            context = json.loads(context_str) if context_str else {}
            domaine = context.get('domaine', 'Mathématiques')
            niveau = context.get('niveau', 'Collège')
            type_exercice = context.get('type_exercice', 'Problème à résoudre')
            attente = context.get('attente', 'Solution étape par étape')
            infos = context.get('infos', '')
            logger.info(f"Contexte: {context}")

            # Appel à Gemini
            ia_response = self.call_gemini_api(image_bytes, domaine, niveau, type_exercice, attente, infos)

            return Response({
                'success': True,
                'data': {
                    'extracted_text': ia_response.get('extracted_text', 'Extrait par Gemini'),
                    'solution': ia_response
                },
                'statusCode': status.HTTP_200_OK
            })
            print(success ,data , statusCode  )
        except json.JSONDecodeError:
            logger.error("Erreur JSON contexte")
            return Response(
                {'success': False, 'message': 'Contexte invalide (format JSON incorrect).'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Erreur générale: {str(e)}")
            return Response(
                {'success': False, 'message': f'Erreur lors du traitement: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def call_gemini_api(self, image_bytes, domaine, niveau, type_exercice, attente, infos):
        # Modèle multimodal stable (Gemini 2.5 Flash - remplace gemini-1.5-flash)
        model = genai.GenerativeModel('gemini-2.5-flash')

        # Construire le prompt avec exemple JSON
        prompt = (
                f"Tu es un assistant pédagogique expert. Analyse cette image d'un exercice de {domaine} pour un niveau {niveau}. "
                f"Type d'exercice: {type_exercice}. "
                f"Attente de l'utilisateur: {attente}. "
                f"Infos supplémentaires: {infos}. "
                f"Instructions : "
                f"1. Extrais le texte de l'image (utilise LaTeX entre $$ pour les équations si présentes, sinon texte brut). "
                f"2. Si l'exercice est de type scientifique (ex. : problème à résoudre, calcul), fournis une solution claire avec étapes détaillées, en formatant les équations en LaTeX (ex. : $$x^2 + 2x + 1 = 0$$). "
                f"3. Si l'exercice est de type littéraire (ex. : rédaction, résumé, traduction), fournis une réponse fluide et concise, adaptée à l'attente (ex. : résumé en 100 mots, traduction en anglais). "
                f"4. Retourne la réponse **UNIQUEMENT** sous forme JSON avec 'extracted_text' (texte brut ou avec LaTeX), 'result' (résultat final ou réponse textuelle), et 'steps' (liste des étapes pour exercices scientifiques, ou liste vide pour exercices littéraires). "
                f"Exemple pour un exercice scientifique : "
                f"```json\n"
                f"{{\n  \"extracted_text\": \"x^2 + 2x + 1 = 0\",\n  \"result\": \"x = -1\",\n  \"steps\": [\"Étape 1: Factorisation $$(x+1)^2 = 0$$\", \"Étape 2: Solution $$x = -1$$\"]\n}}\n```"
                f"Exemple pour un exercice littéraire : "
                f"```json\n"
                f"{{\n  \"extracted_text\": \"Résumez ce poème...\",\n  \"result\": \"Résumé en 100 mots : Le poème parle de...\",\n  \"steps\": []\n}}\n```"
                f"Ne retourne rien d'autre que ce JSON."
            )

        try:
            # Créer le contenu multimodal (texte + image)
            image_part = genai.upload_file(BytesIO(image_bytes), mime_type='image/jpeg')  # Ou 'image/png'
            response = model.generate_content([prompt, image_part])

            # Récupérer la réponse
            content = response.text
            logger.info(f"Réponse Gemini: {content[:200]}...")

            # Parser la réponse JSON
            try:
                result = json.loads(content)
                return {
                    'extracted_text': result.get('extracted_text', 'Extrait par Gemini'),
                    'result': result.get('result', 'Solution calculée'),
                    'steps': result.get('steps', ['Pas d\'étapes disponibles'])
                }
            except json.JSONDecodeError:
                # Fallback : Tente de extraire le JSON du contenu (Gemini peut ajouter du texte)
                start = content.find('{')
                end = content.rfind('}') + 1
                if start != -1 and end != 0:
                    json_str = content[start:end]
                    result = json.loads(json_str)
                    return {
                        'extracted_text': result.get('extracted_text', 'Extrait par Gemini'),
                        'result': result.get('result', 'Solution calculée'),
                        'steps': result.get('steps', ['Pas d\'étapes disponibles'])
                    }
                else:
                    # Dernier fallback
                    return {
                        'extracted_text': 'Extrait par Gemini',
                        'result': content.split('\n')[0] if '\n' in content else content,
                        'steps': content.split('\n')[1:] if '\n' in content else ['Pas d\'étapes disponibles']
                    }
        except Exception as e:
            logger.error(f"Erreur Gemini: {str(e)}")
            raise Exception(f'Erreur API Gemini: {str(e)}')







# import logging
# import json
# import base64
# from io import BytesIO

# import requests
# import pytesseract
# from PIL import Image
# from rest_framework import status
# from rest_framework.views import APIView
# from rest_framework.parsers import MultiPartParser, FormParser
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated

# from .models import ExerciseProcessing  # Optionnel
# from .serializers import ProcessImageSerializer  # Optionnel

# from rest_framework.views import APIView
# from rest_framework.parsers import MultiPartParser, FormParser
# from rest_framework.response import Response
# from rest_framework import status
# from rest_framework.permissions import IsAuthenticated
# import json
# import logging
# import google.generativeai as genai
# from django.conf import settings
# from io import BytesIO

# # Configurer le logging
# logger = logging.getLogger(__name__)

# # Configurer Gemini
# genai.configure(api_key=settings.GEMINI_API_KEY)




# class ProcessImageView(APIView):
#     parser_classes = [MultiPartParser, FormParser]

#     def post(self, request):
#         # Mode test avec image locale (commentez cette partie pour Flutter)
#         TEST_MODE = True  # Change à False pour utiliser avec Flutter
#         if TEST_MODE:
#             image_path = r'C:\git_project\CORRECTION APP BACKEND\treatment\images\imgtest.jpg'
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
#         # Modèle multimodal
#         model = genai.GenerativeModel('gemini-1.5-flash')

#         # Construire le prompt
#         prompt = (
#             f"Tu es un assistant pédagogique expert. Analyse cette image d'un exercice de {domaine} pour un niveau {niveau}. "
#             f"Type d'exercice: {type_exercice}. "
#             f"Attente de l'utilisateur: {attente}. "
#             f"Infos supplémentaires: {infos}. "
#             f"1. Extrais le texte de l'image (équations en LaTeX si possible, entre $$  ). "
#             f"2. Fournis une solution claire et adaptée au niveau, avec étapes détaillées. "
#             f"3. Formate les équations en LaTeX (ex. :   $$x^2 + 2x + 1 = 0$$). "
#             f"Retourne la réponse sous forme JSON avec 'extracted_text' (texte brut), 'result' (résultat final), et 'steps' (liste des étapes)."
#         )

#         try:
#             # Créer le contenu multimodal
#             image_part = {
#                 'mime_type': 'image/jpeg',  # Change à 'image/png' si nécessaire
#                 'data': image_bytes
#             }
#             response = model.generate_content([prompt, image_part], request_options={'response_mime_type': 'application/json'})

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
#                 # Fallback si pas JSON pur
#                 return {
#                     'extracted_text': 'Extrait par Gemini',
#                     'result': content.split('\n')[0] if '\n' in content else content,
#                     'steps': content.split('\n')[1:] if '\n' in content else ['Pas d\'étapes disponibles']
#                 }
#         except Exception as e:
#             logger.error(f"Erreur Gemini: {str(e)}")
#             raise Exception(f'Erreur API Gemini: {str(e)}')



# class ProcessImageView(APIView):
#     parser_classes = [MultiPartParser, FormParser]
#     # permission_classes = [IsAuthenticated]

#     def post(self, request):
#         image = request.FILES.get('image')
#         context_str = request.POST.get('context')

#         if not image:
#             logger.error("Aucune image fournie")
#             return Response(
#                 {'success': False, 'message': 'Aucune image fournie.'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         try:
#             # Parser le contexte
#             context = json.loads(context_str) if context_str else {}
#             domaine = context.get('domaine', 'Mathématiques')
#             niveau = context.get('niveau', 'Collège')
#             type_exercice = context.get('type_exercice', 'Problème à résoudre')
#             attente = context.get('attente', 'Solution étape par étape')
#             infos = context.get('infos', '')
#             logger.info(f"Contexte: {context}")

#             # Encoder l'image en base64
#             image_data = image.read()
#             base64_image = base64.b64encode(image_data).decode('utf-8')

#             # Appel direct à l'IA multimodale (xAI Grok)
#             ia_response = self.call_ia_api(base64_image, domaine, niveau, type_exercice, attente, infos)

#             return Response({
#                 'success': True,
#                 'data': {
#                     'extracted_text': ia_response.get('extracted_text', 'Extrait par l\'IA'),  # Optionnel si IA renvoie ça
#                     'solution': ia_response
#                 },
#                 'statusCode': status.HTTP_200_OK
#             })
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

    # def call_ia_api(self, base64_image, domaine, niveau, type_exercice, attente, infos):
    #     # Prompt pour l'IA multimodale
    #     prompt = (
    #         f"Analyse cette image d'exercice de {domaine} pour un niveau {niveau}. "
    #         f"Type d'exercice: {type_exercice}. "
    #         f"Attente de l'utilisateur: {attente}. "
    #         f"Infos supplémentaires: {infos}. "
    #         f"Extrais le texte, comprends l'exercice, et fournis une correction adaptée."
    #     )

    #     # Appel à xAI API (Grok 4, multimodal)
    #     xai_url = 'https://api.x.ai/v1/chat/completions'  # Ou l'endpoint pour Grok 4
    #     payload = {
    #         'model': 'grok-beta',  # Ou 'grok-4' si disponible
    #         'messages': [
    #             {'role': 'user', 'content': [
    #                 {'type': 'text', 'text': prompt},
    #                 {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{base64_image}'}}
    #             ]}
    #         ],
    #         'max_tokens': 500,
    #         'temperature': 0.7
    #     }
    #     headers = {
    #         'Authorization': 'Bearer YOUR_XAI_API_KEY',  # Remplace par ta clé
    #         'Content-Type': 'application/json'
    #     }
    #     response = requests.post(xai_url, json=payload, headers=headers)
    #     if response.status_code == 200:
    #         content = response.json()['choices'][0]['message']['content']
    #         # Parse la réponse (ex. : assume format JSON ou texte)
    #         return {
    #             'result': content.split('\n')[0],
    #             'steps': content.split('\n')[1:]
    #         }
    #     else:
    #         raise Exception(f'Erreur xAI API: {response.status_code} - {response.text}')