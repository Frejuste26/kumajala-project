import os
import base64
import hashlib
import logging
from typing import Optional, Dict, Any
from gtts import gTTS
from gtts.lang import tts_langs
from io import BytesIO

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TTSService:
    def __init__(self):
        """
        Initialise le service de synthèse vocale gTTS avec cache et validation.
        
        ATTENTION: gTTS ne supporte PAS les langues africaines locales (Bété, Baoulé, Mooré, Agni).
        Les traductions dans ces langues seront prononcées avec l'accent français.
        
        Solutions alternatives recommandées:
        - Google Cloud Text-to-Speech (support de plus de langues)
        - Azure Speech Services
        - Enregistrements audio pré-générés par des locuteurs natifs
        - Système de phonétique personnalisé
        """
        try:
            # Récupérer les langues supportées par gTTS
            self.supported_languages = tts_langs()
            self.is_available = True
            
            # Cache pour les audios générés
            self._audio_cache: Dict[str, bytes] = {}
            self._cache_max_size = 100  # Limite de 100 audios en cache
            
            logger.info(f"Service gTTS initialisé avec succès ({len(self.supported_languages)} langues supportées)")
            logger.warning("⚠️ AVERTISSEMENT: gTTS ne supporte pas les langues africaines locales (Bété, Baoulé, Mooré, Agni)")
            logger.info(f"Langues supportées: {', '.join(sorted(self.supported_languages.keys())[:10])}...")
            
        except Exception as e:
            logger.error(f"Erreur d'initialisation gTTS: {e}")
            self.supported_languages = {}
            self.is_available = False
            self._audio_cache = {}

    def _get_cache_key(self, text: str, language_code: str) -> str:
        """Génère une clé de cache unique basée sur le texte et la langue"""
        content = f"{text}:{language_code}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _manage_cache_size(self):
        """Gère la taille du cache en supprimant les entrées les plus anciennes"""
        if len(self._audio_cache) >= self._cache_max_size:
            # Supprimer 20% des entrées les plus anciennes (simple FIFO)
            keys_to_remove = list(self._audio_cache.keys())[:self._cache_max_size // 5]
            for key in keys_to_remove:
                del self._audio_cache[key]
            logger.debug(f"Cache nettoyé: {len(keys_to_remove)} entrées supprimées")

    def synthesize_speech(self, text: str, language_code: str = "fr", use_cache: bool = True) -> Dict[str, Any]:
        """
        Synthétise la parole à partir du texte en utilisant gTTS.
        
        Args:
            text: Texte à synthétiser
            language_code: Code langue ISO 639-1 (ex: 'fr', 'en') ou code personnalisé
            use_cache: Utiliser le cache pour éviter de régénérer les mêmes audios
            
        Returns:
            Dict avec success, audio_base64, content_type, ou error
        """
        if not self.is_available:
            return {
                'success': False,
                'error': "Service TTS non disponible (gTTS initialisation échouée)"
            }

        # Validation du texte
        if not text or not text.strip():
            return {
                'success': False,
                'error': "Le texte à synthétiser ne peut pas être vide."
            }

        # Validation de la longueur du texte
        if len(text) > 5000:
            return {
                'success': False,
                'error': "Le texte est trop long (max 5000 caractères)"
            }

        try:
            # Extraire le code langue principal (ex: 'fr-FR' -> 'fr')
            lang_code_simple = language_code.split('-')[0].lower()

            # Vérifier si la langue est supportée par gTTS
            if lang_code_simple not in self.supported_languages:
                # Avertissement spécial pour les langues africaines
                african_languages = ['bété', 'baoulé', 'mooré', 'agni']
                if lang_code_simple in african_languages:
                    logger.warning(
                        f"⚠️ Langue '{lang_code_simple}' non supportée par gTTS. "
                        f"Utilisation du français par défaut. "
                        f"Le texte sera prononcé avec un accent français."
                    )
                    lang_code_simple = 'fr'
                else:
                    return {
                        'success': False,
                        'error': f"Langue '{lang_code_simple}' non supportée par gTTS",
                        'supported_languages': list(self.supported_languages.keys())
                    }

            # Vérifier le cache
            cache_key = self._get_cache_key(text, lang_code_simple)
            if use_cache and cache_key in self._audio_cache:
                logger.debug(f"Cache hit pour TTS: {text[:30]}...")
                audio_bytes = self._audio_cache[cache_key]
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                
                return {
                    'success': True,
                    'audio_base64': audio_base64,
                    'content_type': 'audio/mpeg',
                    'text': text,
                    'language_code': language_code,
                    'actual_tts_language': lang_code_simple,
                    'cached': True
                }

            # Générer l'audio avec gTTS
            logger.info(f"Génération TTS pour: '{text[:50]}...' en {lang_code_simple}")
            
            tts = gTTS(
                text=text,
                lang=lang_code_simple,
                slow=False  # Vitesse normale
            )

            # Écrire dans un buffer mémoire
            audio_buffer = BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            
            # Lire les bytes
            audio_bytes = audio_buffer.read()
            
            # Vérifier que l'audio n'est pas vide
            if len(audio_bytes) == 0:
                return {
                    'success': False,
                    'error': "Audio généré est vide"
                }

            # Gérer la taille du cache
            if use_cache:
                self._manage_cache_size()
                self._audio_cache[cache_key] = audio_bytes

            # Encoder en base64
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

            logger.info(f"Audio généré avec succès ({len(audio_bytes)} bytes)")

            return {
                'success': True,
                'audio_base64': audio_base64,
                'content_type': 'audio/mpeg',
                'text': text,
                'language_code': language_code,
                'actual_tts_language': lang_code_simple,
                'audio_size_bytes': len(audio_bytes),
                'cached': False
            }

        except Exception as e:
            logger.error(f"Erreur lors de la synthèse TTS pour '{text[:50]}...' en {language_code}: {e}")
            return {
                'success': False,
                'error': f"Erreur lors de la génération audio: {str(e)}"
            }

    def get_supported_languages(self) -> Dict[str, str]:
        """
        Retourne la liste des langues supportées par gTTS.
        
        Returns:
            Dict avec code langue -> nom de la langue
        """
        return self.supported_languages.copy()

    def is_language_supported(self, language_code: str) -> bool:
        """
        Vérifie si une langue est supportée par gTTS.
        
        Args:
            language_code: Code langue à vérifier
            
        Returns:
            True si supportée, False sinon
        """
        lang_code_simple = language_code.split('-')[0].lower()
        return lang_code_simple in self.supported_languages

    def clear_cache(self):
        """Vide le cache audio"""
        cache_size = len(self._audio_cache)
        self._audio_cache.clear()
        logger.info(f"Cache audio vidé ({cache_size} entrées supprimées)")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Retourne des statistiques sur le cache"""
        total_size_bytes = sum(len(audio) for audio in self._audio_cache.values())
        return {
            'entries': len(self._audio_cache),
            'max_entries': self._cache_max_size,
            'total_size_bytes': total_size_bytes,
            'total_size_mb': round(total_size_bytes / (1024 * 1024), 2)
        }

    def is_service_available(self) -> bool:
        """Vérifie si le service TTS est disponible"""
        return self.is_available

    def get_recommended_alternatives(self) -> Dict[str, Any]:
        """
        Retourne des recommandations pour supporter les langues africaines.
        
        Returns:
            Dict avec les alternatives recommandées
        """
        return {
            'issue': 'gTTS ne supporte pas les langues africaines locales (Bété, Baoulé, Mooré, Agni)',
            'current_behavior': 'Les textes sont prononcés en français avec accent français',
            'recommended_solutions': [
                {
                    'name': 'Google Cloud Text-to-Speech',
                    'url': 'https://cloud.google.com/text-to-speech',
                    'pros': 'Support de nombreuses langues, voix naturelles, API robuste',
                    'cons': 'Payant après quota gratuit'
                },
                {
                    'name': 'Azure Speech Services',
                    'url': 'https://azure.microsoft.com/services/cognitive-services/text-to-speech',
                    'pros': 'Support multilingue, qualité professionnelle',
                    'cons': 'Payant'
                },
                {
                    'name': 'Enregistrements audio natifs',
                    'pros': 'Authentique, meilleure qualité culturelle',
                    'cons': 'Nécessite des locuteurs natifs, coûteux en temps'
                },
                {
                    'name': 'Coqui TTS (open-source)',
                    'url': 'https://github.com/coqui-ai/TTS',
                    'pros': 'Open-source, personnalisable, peut être entraîné',
                    'cons': 'Nécessite expertise ML et données d\'entraînement'
                }
            ],
            'temporary_solution': 'Utiliser gTTS avec français et indiquer clairement aux utilisateurs que la prononciation n\'est pas authentique'
        }