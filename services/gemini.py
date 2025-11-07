import os
import logging
import re
from typing import Optional
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GeminiService:
    def __init__(self):
        """Initialise le service Gemini avec retry et validation"""
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.warning("GEMINI_API_KEY non définie. Service Gemini indisponible.")
            self.is_available = False
            return

        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            # Configuration de génération par défaut
            self.generation_config = genai.GenerationConfig(
                max_output_tokens=200,
                temperature=0.2,  # Plus déterministe pour les traductions
                top_p=0.8,
                top_k=40
            )
            
            self.is_available = True
            logger.info("Service Gemini initialisé avec succès")
        except Exception as e:
            logger.error(f"Erreur d'initialisation Gemini: {e}")
            self.is_available = False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True
    )
    def translate_text(self, text: str, target_language: str) -> Optional[str]:
        """Traduit un texte avec retry, timeout et validation"""
        if not self.is_available:
            logger.debug("GeminiService non disponible, skipping translation.")
            return None

        if not text or not text.strip():
            logger.warning("Texte vide fourni pour traduction")
            return None

        try:
            prompt = self._build_translation_prompt(text, target_language)
            
            logger.debug(f"Traduction Gemini: '{text[:50]}...' -> {target_language}")
            
            # Génération avec configuration
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config,
                request_options={'timeout': 30}
            )

            # Extraction sécurisée de la traduction
            translation = self._extract_translation_from_response(response)

            if not translation:
                logger.warning(f"Aucune traduction extraite pour '{text}'")
                return None

            # Validation de la traduction
            if not self._validate_translation(text, translation, target_language):
                logger.warning(f"Traduction invalide pour '{text}' -> {target_language}")
                return None

            logger.info(f"Traduction réussie: '{text[:30]}...' -> '{translation[:30]}...'")
            return translation

        except Exception as e:
            logger.error(f"Erreur lors de la traduction Gemini: {e}")
            raise  # Re-raise pour permettre le retry

    def _extract_translation_from_response(self, response) -> Optional[str]:
        """Extrait la traduction de la réponse Gemini de manière robuste"""
        try:
            # Vérification de la structure de base
            if not hasattr(response, 'candidates') or not response.candidates:
                logger.warning("Réponse sans candidates")
                return None

            candidate = response.candidates[0]
            
            # Vérifier le contenu
            if not hasattr(candidate, 'content') or not candidate.content:
                logger.warning("Candidate sans content")
                return None

            # Vérifier les parts
            if not hasattr(candidate.content, 'parts') or not candidate.content.parts:
                logger.warning("Content sans parts")
                return None

            # Extraire et concaténer tout le texte
            translated_content = ""
            for part in candidate.content.parts:
                if hasattr(part, 'text'):
                    translated_content += part.text

            if not translated_content:
                logger.warning("Aucun texte dans les parts")
                return None

            # Nettoyer la réponse
            translation = self._clean_response(translated_content)

            # Vérifier les marqueurs d'impossibilité
            impossibility_markers = [
                "traduction_impossible",
                "cannot translate",
                "unable to translate",
                "impossible de traduire"
            ]
            
            if any(marker in translation.lower() for marker in impossibility_markers):
                logger.info("Gemini a indiqué que la traduction est impossible")
                return None

            return translation

        except (IndexError, AttributeError) as e:
            logger.error(f"Erreur lors de l'extraction de la traduction: {e}")
            return None

    def _clean_response(self, response: str) -> str:
        """Nettoie la réponse de Gemini pour extraire uniquement la traduction"""
        response = response.strip()

        # Supprimer les guillemets au début et à la fin
        if (response.startswith('"') and response.endswith('"')) or \
           (response.startswith("'") and response.endswith("'")):
            response = response[1:-1].strip()

        # Liste exhaustive de préfixes à supprimer
        prefixes_to_remove = [
            r'^traduction\s*:?\s*',
            r'^translation\s*:?\s*',
            r'^réponse\s*:?\s*',
            r'^response\s*:?\s*',
            r'^en\s+\w+\s*:?\s*',
            r'^le texte traduit est\s*:?\s*',
            r'^voici la traduction\s+(?:en\s+\w+)?\s*:?\s*',
            r'^la traduction est\s*:?\s*',
            r'^traduction en\s+\w+\s*:?\s*',
            r'^la traduction de\s+.*?en\s+\w+\s+est\s*:?\s*',
            r'^\w+\s*:\s*',  # Capture "Baoulé: " etc.
        ]

        for prefix_pattern in prefixes_to_remove:
            response = re.sub(prefix_pattern, '', response, flags=re.IGNORECASE)
            response = response.strip()

        # Supprimer les explications après la traduction
        # (ex: "Akwaba (cela signifie...)")
        response = re.split(r'\s*[\(\[].*?[\)\]]', response)[0].strip()

        # Supprimer les points finaux si présents (souvent ajoutés par erreur)
        if response.endswith('.') and not response.endswith('...'):
            response = response[:-1].strip()

        return response

    def _validate_translation(self, source: str, translation: str, target_language: str) -> bool:
        """Valide que la traduction est cohérente et de qualité"""
        
        # Vérification de base
        if not translation or len(translation.strip()) < 1:
            logger.debug("Traduction vide ou trop courte")
            return False

        # La traduction ne doit pas être identique à la source
        if translation.lower().strip() == source.lower().strip():
            logger.debug("Traduction identique à la source")
            return False

        # Vérifier la longueur relative (0.2x à 5x)
        source_len = len(source.strip())
        trans_len = len(translation.strip())
        
        if source_len == 0:
            return False
            
        length_ratio = trans_len / source_len
        
        if not (0.2 <= length_ratio <= 5.0):
            logger.debug(f"Ratio de longueur suspect: {length_ratio:.2f}")
            return False

        # Vérifier qu'il n'y a pas trop de mots français (plus de 30%)
        french_indicators = [
            'le', 'la', 'les', 'un', 'une', 'des', 'et', 'ou', 'de', 'du',
            'au', 'aux', 'est', 'sont', 'avec', 'pour', 'dans', 'sur'
        ]
        
        translation_words = translation.lower().split()
        if len(translation_words) > 3:  # Seulement pour les phrases longues
            french_word_count = sum(1 for word in translation_words if word in french_indicators)
            french_ratio = french_word_count / len(translation_words)
            
            if french_ratio > 0.3:
                logger.debug(f"Trop de mots français détectés ({french_ratio:.2%})")
                return False

        # Vérifier qu'il n'y a pas de marqueurs d'erreur
        error_markers = [
            "erreur", "error", "impossible", "cannot", "unable",
            "je ne peux pas", "i cannot", "désolé", "sorry",
            "traduction non disponible", "translation unavailable"
        ]
        
        translation_lower = translation.lower()
        if any(marker in translation_lower for marker in error_markers):
            logger.debug("Marqueur d'erreur détecté dans la traduction")
            return False

        # Vérifier qu'il n'y a pas trop de caractères spéciaux inhabituels
        special_char_count = sum(1 for char in translation if not char.isalnum() and char not in ' .,!?-\'')
        special_char_ratio = special_char_count / len(translation)
        
        if special_char_ratio > 0.3:
            logger.debug(f"Trop de caractères spéciaux ({special_char_ratio:.2%})")
            return False

        return True

    def _build_translation_prompt(self, text: str, target_language: str) -> str:
        """Construit un prompt optimisé avec few-shot learning"""
        
        # Contextes enrichis pour chaque langue
        language_contexts = {
            'bété': {
                'description': 'langue Kru parlée principalement en Côte d\'Ivoire, dans les régions de Gagnoa et Daloa',
                'examples': [
                    'Bonjour → Akwaba',
                    'Merci → Akpé',
                    'Au revoir → Kan na',
                    'Oui → Yoo',
                    'Non → Kou',
                    'Comment allez-vous? → Bi ye né?',
                    'Ça va → Bi dè',
                    'Eau → Nyɛ'
                ],
                'notes': 'Le Bété utilise des tons et des nasales. Respecte les accents et les caractères spéciaux.'
            },
            'baoulé': {
                'description': 'langue akan parlée en Côte d\'Ivoire, principalement dans la région du centre (Yamoussoukro, Bouaké)',
                'examples': [
                    'Bonjour → Mo ho',
                    'Merci → Mo',
                    'Au revoir → Kan na',
                    'Oui → Yoo',
                    'Non → Kou',
                    'Comment allez-vous? → Wo ho tè n?',
                    'Je m\'appelle → Man yi tɔ',
                    'Maison → Kpè'
                ],
                'notes': 'Le Baoulé est une langue tonale avec des voyelles nasales.'
            },
            'mooré': {
                'description': 'langue Gur parlée principalement au Burkina Faso par le peuple Mossi, également parlée au Ghana et au Togo',
                'examples': [
                    'Bonjour → Ne y windga',
                    'Merci → Barika',
                    'Au revoir → Nan kã pãalem',
                    'Oui → Yãa',
                    'Non → Ayi',
                    'Comment allez-vous? → Fo laafi?',
                    'Bonne nuit → Sẽn-doogo',
                    'Eau → Koom'
                ],
                'notes': 'Le Mooré utilise des nasales marquées par des tildes (~).'
            },
            'agni': {
                'description': 'langue akan parlée principalement en Côte d\'Ivoire dans la région Est (Abengourou, Agnibilékrou)',
                'examples': [
                    'Bonjour → Agni oh',
                    'Merci → Akpé',
                    'Au revoir → Aka na',
                    'Oui → Aoo',
                    'Non → N\'an',
                    'Comment allez-vous? → Aka kye?',
                    'Maison → Aso',
                    'Eau → Nsu'
                ],
                'notes': 'L\'Agni est proche du Baoulé mais avec des variations dialectales.'
            }
        }

        context = language_contexts.get(target_language, {
            'description': f'langue africaine locale: {target_language}',
            'examples': [],
            'notes': ''
        })

        examples_text = '\n'.join(f'  - {ex}' for ex in context['examples'])

        prompt = f"""Tu es un expert linguiste spécialisé dans les langues africaines locales.

            LANGUE CIBLE: {target_language}
            Description: {context['description']}

            EXEMPLES DE TRADUCTIONS FRANÇAISES → {target_language.upper()}:
            {examples_text}

            NOTES IMPORTANTES:
            - {context['notes']}

            TEXTE À TRADUIRE:
            "{text}"

            INSTRUCTIONS STRICTES:
            1. Traduis le texte français ci-dessus en {target_language}
            2. Fournis UNIQUEMENT la traduction, sans aucun préfixe, explication ou commentaire
            3. Ne mets pas de guillemets autour de ta réponse
            4. Respecte strictement la grammaire et les tons du {target_language}
            5. Utilise les caractères spéciaux appropriés (accents, tildes, etc.)
            6. Si la traduction est impossible ou que tu n'es pas sûr, réponds exactement: TRADUCTION_IMPOSSIBLE

        TRADUCTION:"""

        return prompt

    def is_service_available(self) -> bool:
        """Vérifie si le service Gemini est disponible"""
        return self.is_available