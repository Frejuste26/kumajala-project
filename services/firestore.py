import os
import logging
import hashlib
import json
from typing import Optional, Dict, List
from google.cloud import firestore
from datetime import datetime, timedelta

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FirestoreService:
    def __init__(self):
        """Initialise le service Firestore avec cache et gestion d'erreurs robuste"""
        # Cache en mémoire pour les traductions
        self._translation_cache: Dict[str, Dict[str, any]] = {}
        self._cache_ttl = timedelta(hours=1)
        
        # Initialisation du client Firestore
        if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            logger.warning("GOOGLE_APPLICATION_CREDENTIALS non définie. Utilisation des données locales.")
            self.use_local_data = True
            self.load_local_translations()
        else:
            try:
                self.db = firestore.Client()
                self.use_local_data = False
                logger.info("Service Firestore initialisé avec succès.")
            except Exception as e:
                logger.error(f"Erreur connexion Firestore: {e}. Fallback vers les données locales.")
                self.use_local_data = True
                self.load_local_translations()

        # Métadonnées des langues supportées
        self._language_metadata = {
            'bété': {'code': 'bété', 'name': 'Bété', 'region': 'Côte d\'Ivoire', 'code_tts': 'fr'},
            'baoulé': {'code': 'baoulé', 'name': 'Baoulé', 'region': 'Côte d\'Ivoire', 'code_tts': 'fr'},
            'mooré': {'code': 'mooré', 'name': 'Mooré', 'region': 'Burkina Faso', 'code_tts': 'fr'},
            'agni': {'code': 'agni', 'name': 'Agni', 'region': 'Côte d\'Ivoire', 'code_tts': 'fr'},
            'fr': {'code': 'fr', 'name': 'Français', 'region': 'Global', 'code_tts': 'fr'}
        }

    def load_local_translations(self):
        """Charge les traductions depuis le fichier JSON local avec validation"""
        try:
            script_dir = os.path.dirname(__file__)
            json_path = os.path.join(script_dir, '..', 'data', 'language.json')

            with open(json_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
                
            # Validation et normalisation de la structure
            if not isinstance(raw_data, dict):
                logger.error("Structure JSON invalide: doit être un dictionnaire")
                self._initialize_default_translations()
                return
            
            # S'assurer que la structure "fr" existe
            if "fr" not in raw_data:
                logger.warning("Clé 'fr' absente. Restructuration des données.")
                # Si les données sont directement les traductions, les encapsuler
                self.local_translations = {"fr": raw_data}
            else:
                self.local_translations = {"fr": {}}
                # Normaliser toutes les clés en minuscules
                for key, value in raw_data["fr"].items():
                    if isinstance(value, dict):
                        self.local_translations["fr"][key.lower()] = value
                    else:
                        logger.warning(f"Entrée invalide ignorée: {key}")
            
            logger.info(f"Traductions locales chargées depuis {json_path} ({len(self.local_translations.get('fr', {}))} entrées)")

        except FileNotFoundError:
            logger.warning("Fichier data/language.json non trouvé. Création de données par défaut.")
            self._initialize_default_translations()
            self._save_local_translations_to_file()
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de parsing JSON: {e}")
            self._initialize_default_translations()
        except Exception as e:
            logger.error(f"Erreur lors du chargement des traductions locales: {e}")
            self._initialize_default_translations()

    def _initialize_default_translations(self):
        """Initialise les traductions par défaut"""
        self.local_translations = {
            "fr": {
                "bonjour": {
                    "bété": "Akwaba", "baoulé": "Mo ho", "mooré": "Ne y windga", "agni": "Agni oh"
                },
                "comment allez-vous?": {
                    "bété": "Bi ye né?", "baoulé": "Wo ho tè n?", "mooré": "Fo laafi?", "agni": "Aka kye?"
                },
                "merci": {
                    "bété": "Akpé", "baoulé": "Mo", "mooré": "Barika", "agni": "Akpé"
                },
                "au revoir": {
                    "bété": "Kan na", "baoulé": "Kan na", "mooré": "Nan kã pãalem", "agni": "Aka na"
                },
                "oui": {
                    "bété": "Yoo", "baoulé": "Yoo", "mooré": "Yãa", "agni": "Aoo"
                },
                "non": {
                    "bété": "Kou", "baoulé": "Kou", "mooré": "Ayi", "agni": "N'an"
                }
            }
        }

    def _save_local_translations_to_file(self):
        """Sauvegarde les données locales dans le fichier JSON de manière asynchrone"""
        try:
            script_dir = os.path.dirname(__file__)
            json_path = os.path.join(script_dir, '..', 'data', 'language.json')
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(self.local_translations, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Traductions locales sauvegardées dans {json_path}.")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des traductions locales: {e}")

    def _get_cache_key(self, text: str, target_language: str) -> str:
        """Génère une clé de cache unique"""
        return f"{text.lower()}:{target_language}"

    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """Vérifie si l'entrée du cache est encore valide"""
        if 'timestamp' not in cache_entry:
            return False
        cache_age = datetime.now() - cache_entry['timestamp']
        return cache_age < self._cache_ttl

    def get_translation(self, text: str, target_language: str) -> Optional[str]:
        """Récupère une traduction avec cache et validation"""
        if not text or not text.strip():
            logger.warning("Texte vide fourni pour traduction")
            return None
        
        # Validation de la langue cible
        if target_language not in self._language_metadata:
            logger.warning(f"Langue non supportée: {target_language}")
            return None
        
        # Vérifier le cache d'abord
        cache_key = self._get_cache_key(text, target_language)
        if cache_key in self._translation_cache:
            cache_entry = self._translation_cache[cache_key]
            if self._is_cache_valid(cache_entry):
                logger.debug(f"Cache hit pour: {text} -> {target_language}")
                return cache_entry['translation']
            else:
                # Invalider le cache expiré
                del self._translation_cache[cache_key]
        
        # Récupération depuis la source
        text_lower = text.lower()
        translation = (
            self._get_local_translation(text_lower, target_language)
            if self.use_local_data
            else self._get_firestore_translation(text_lower, target_language)
        )
        
        # Mise en cache si traduction trouvée
        if translation:
            self._translation_cache[cache_key] = {
                'translation': translation,
                'timestamp': datetime.now()
            }
        
        return translation

    def _get_local_translation(self, text_lower: str, target_language: str) -> Optional[str]:
        """Récupère une traduction depuis les données locales"""
        try:
            translations = self.local_translations.get("fr", {})
            if text_lower in translations:
                lang_translations = translations[text_lower]
                if isinstance(lang_translations, dict) and target_language in lang_translations:
                    return lang_translations[target_language]
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération locale: {e}")
            return None

    def _get_firestore_translation(self, text_lower: str, target_language: str) -> Optional[str]:
        """Récupère une traduction depuis Firestore avec gestion d'erreurs"""
        try:
            # Utiliser un hash pour les clés trop longues ou avec caractères spéciaux
            doc_id = self._get_document_id(text_lower)
            doc_ref = self.db.collection('translations').document(doc_id)
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                # Vérifier que la structure est correcte
                if 'languages' in data and isinstance(data['languages'], dict):
                    return data['languages'].get(target_language)
                # Ancien format pour rétrocompatibilité
                return data.get(target_language)
            
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération Firestore: {e}")
            return None

    def _get_document_id(self, text: str) -> str:
        """Génère un ID de document sécurisé"""
        # Pour les textes courts sans caractères spéciaux, utiliser directement
        if len(text) <= 100 and text.replace(' ', '').replace('-', '').isalnum():
            return text.lower().replace(' ', '_')
        # Sinon, utiliser un hash
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def save_translation(self, text: str, target_language: str, translation: str) -> bool:
        """Sauvegarde une traduction avec invalidation du cache"""
        if not text or not translation:
            logger.warning("Texte ou traduction vide")
            return False
        
        if target_language not in self._language_metadata:
            logger.warning(f"Langue non supportée: {target_language}")
            return False
        
        # Invalider le cache
        cache_key = self._get_cache_key(text, target_language)
        self._translation_cache.pop(cache_key, None)
        
        text_lower = text.lower()
        success = (
            self._save_local_translation(text_lower, target_language, translation)
            if self.use_local_data
            else self._save_firestore_translation(text_lower, target_language, translation)
        )
        
        return success

    def _save_local_translation(self, text_lower: str, target_language: str, translation: str) -> bool:
        """Sauvegarde une traduction localement"""
        try:
            if "fr" not in self.local_translations:
                self.local_translations["fr"] = {}

            if text_lower not in self.local_translations["fr"]:
                self.local_translations["fr"][text_lower] = {}

            self.local_translations["fr"][text_lower][target_language] = translation
            self._save_local_translations_to_file()
            
            logger.info(f"Traduction locale sauvegardée: {text_lower} -> {target_language}")
            return True
        except Exception as e:
            logger.error(f"Erreur sauvegarde locale: {e}")
            return False

    def _save_firestore_translation(self, text_lower: str, target_language: str, translation: str) -> bool:
        """Sauvegarde une traduction dans Firestore avec structure améliorée"""
        try:
            doc_id = self._get_document_id(text_lower)
            doc_ref = self.db.collection('translations').document(doc_id)
            
            # Structure hiérarchique améliorée
            doc_ref.set({
                'source': 'fr',
                'text': text_lower,
                'languages': {
                    target_language: translation
                },
                'metadata': {
                    'updated_at': firestore.SERVER_TIMESTAMP,
                    'version': 1
                }
            }, merge=True)
            
            logger.info(f"Traduction Firestore sauvegardée: {text_lower} -> {target_language}")
            return True
        except Exception as e:
            logger.error(f"Erreur sauvegarde Firestore: {e}")
            return False

    def update_translation_manual(self, french_text: str, target_language: str, new_translation: str) -> bool:
        """Met à jour ou ajoute manuellement une traduction avec validation"""
        if not french_text or not new_translation:
            logger.warning("Texte ou traduction vide")
            return False
        
        if target_language not in self._language_metadata:
            logger.warning(f"Langue non supportée: {target_language}")
            return False
        
        logger.info(f"Mise à jour manuelle: '{french_text}' en '{target_language}' = '{new_translation}'")
        return self.save_translation(french_text, target_language, new_translation)

    def get_supported_languages(self) -> List[Dict[str, str]]:
        """Retourne la liste des langues supportées"""
        return sorted(self._language_metadata.values(), key=lambda x: x['name'])

    def clear_cache(self):
        """Vide le cache de traductions"""
        self._translation_cache.clear()
        logger.info("Cache de traductions vidé")

    def get_cache_stats(self) -> Dict[str, int]:
        """Retourne des statistiques sur le cache"""
        total = len(self._translation_cache)
        valid = sum(1 for entry in self._translation_cache.values() if self._is_cache_valid(entry))
        return {
            'total_entries': total,
            'valid_entries': valid,
            'expired_entries': total - valid
        }