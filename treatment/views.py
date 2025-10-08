from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import pytesseract
from PIL import Image
import requests
import json
from io import BytesIO
from .models import ExerciseProcessing  # Optionnel
from .serializers import ProcessImageSerializer  # Optionnel

# Forcer le chemin de Tesseract pour Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class ProcessImageView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        image = request.FILES.get('image')
        context_str = request.POST.get('context')

        # Vérifier si l'image est fournie
        if not image:
            logger.error("Aucune image fournie dans la requête")
            return Response(
                {'success': False, 'message': 'Aucune image fournie.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Vérifier si Tesseract est accessible
            try:
                tesseract_version = pytesseract.get_tesseract_version()
                logger.info(f"Tesseract version: {tesseract_version}")
            except Exception as e:
                logger.error(f"Erreur Tesseract: {str(e)}")
                return Response(
                    {'success': False, 'message': f'Tesseract non accessible: {str(e)}. Vérifiez C:\\Program Files\\Tesseract-OCR\\tesseract.exe.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # OCR
            try:
                image_obj = Image.open(image)
                # Prétraite l'image pour meilleure précision
                image_obj = image_obj.convert('L')  # Grayscale
                text = pytesseract.image_to_string(image_obj, lang='fra+eng', config='--psm 6')
                logger.info(f"Texte extrait: {text[:100]}...")
                if not text.strip():
                    logger.warning("Aucun texte extrait de l'image")
                    return Response(
                        {'success': False, 'message': 'Aucun texte extrait. Vérifiez la qualité de l\'image.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Exception as ocr_error:
                logger.error(f"Erreur OCR: {str(ocr_error)}")
                return Response(
                    {'success': False, 'message': f'Erreur lors de l\'OCR: {str(ocr_error)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Parser le contexte
            try:
                context = json.loads(context_str) if context_str else {}
                domaine = context.get('domaine', 'Mathématiques')
                niveau = context.get('niveau', 'Collège')
                type_exercice = context.get('type_exercice', 'Problème à résoudre')
                attente = context.get('attente', 'Solution étape par étape')
                infos = context.get('infos', '')
                logger.info(f"Contexte: {context}")
            except json.JSONDecodeError as e:
                logger.error(f"Erreur JSON contexte: {str(e)}")
                return Response(
                    {'success': False, 'message': 'Contexte invalide (format JSON incorrect).'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Appel à l'API IA
            try:
                ia_response = self.call_ia_api(text, domaine, niveau, type_exercice, attente, infos)
                logger.info(f"Réponse IA: {ia_response}")
            except Exception as ia_error:
                logger.error(f"Erreur IA: {str(ia_error)}")
                return Response(
                    {'success': False, 'message': f'Erreur lors de l\'appel à l\'API IA: {str(ia_error)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            return Response({
                'success': True,
                'data': {
                    'extracted_text': text,
                    'solution': ia_response
                },
                'statusCode': status.HTTP_200_OK
            })
        except Exception as e:
            logger.error(f"Erreur générale: {str(e)}")
            return Response(
                {'success': False, 'message': f'Erreur lors du traitement: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def call_ia_api(self, text, domaine, niveau, type_exercice, attente, infos):
        prompt = (
            f"Corrige cet exercice de {domaine} pour un niveau {niveau}. "
            f"Type d'exercice: {type_exercice}. "
            f"Attente de l'utilisateur: {attente}. "
            f"Infos supplémentaires: {infos}. "
            f"Exercice extrait: {text}. "
            f"Réponds de manière adaptée au niveau et au type d'exercice."
        )
        logger.info(f"Prompt IA: {prompt[:200]}...")

        # Exemple avec Wolfram Alpha
        wolfram_url = 'https://api.wolframalpha.com/v2/query'
        params = {
            'input': prompt,
            'appid': 'YOUR_WOLFRAM_API_KEY',  # Remplace par ta clé
            'output': 'json',
            'format': 'plaintext'
        }
        response = requests.get(wolfram_url, params=params)
        if response.status_code == 200:
            data = response.json()
            pods = data.get('queryresult', {}).get('pods', [])
            result_text = ''
            steps = []
            for pod in pods[:3]:
                subpods = pod.get('subpods', [])
                for subpod in subpods:
                    plaintext = subpod.get('plaintext', '')
                    if plaintext:
                        if not result_text:
                            result_text = plaintext
                        else:
                            steps.append(plaintext)
            return {
                'result': result_text or 'Solution calculée.',
                'steps': steps or ['Pas d\'étapes disponibles.']
            }
        else:
            raise Exception(f'Erreur API IA: {response.status_code}')