# Traduction de Bandes Dessinées

https://github.com/ogkalu2/comic-translate/assets/115248977/b57360d3-eaad-4a93-bc46-94c01d38927c

## Introduction
De nombreux traducteurs automatiques de mangas existent. Très peu prennent correctement en charge les bandes dessinées d'autres types dans d'autres langues.
Ce projet a été créé pour utiliser les capacités du GPT-4 et traduire des bandes dessinées du monde entier. Actuellement, il prend en charge la traduction vers et depuis l'anglais, le coréen, le japonais, le français, le chinois simplifié, le chinois traditionnel, le russe, l'allemand, le néerlandais, l'espagnol et l'italien.

- [État Actuel de la Traduction Automatique](#état-actuel-de-la-traduction-automatique)
- [Aperçu](#échantillons-de-bandes-dessinées)
- [Pour Commencer](#installation)
    - [Installation](#installation)
        - [Python](#python)
    - [Utilisation](#utilisation)
        - [Conseils](#conseils)
    - [Clés API](#clés-api)
        - [Obtenir des Clés API](#obtenir-des-clés-api)
            - [Open AI](#open-ai-gpt)
            - [Google Cloud Vision](#google-cloud-vision)

- [Fonctionnement](#fonctionnement)
    - [Détection de Texte](#détection-de-texte)
    - [OCR](#ocr)
    - [Effacement](#effacement)
    - [Traduction](#traduction)
    - [Rendu de Texte](#rendu-de-texte)

- [Remerciements](#remerciements)

## État Actuel de la Traduction Automatique
Pour une couple de douzaines de langues, le meilleur traducteur automatique n'est ni Google Translate, ni Papago, ni même DeepL, mais GPT-4, et de loin.
Cela est très évident pour les paires de langues éloignées (coréen <-> anglais, japonais <-> anglais, etc.) où les autres traducteurs dégénèrent souvent en charabia.
Extrait de "Généalogie du mal" (종의 기원) de You-Jeong Jeong (정유정)
![Modèle](https://i.imgur.com/Bizgu6C.jpg)

## Échantillons de Bandes Dessinées
GPT-4-Vision en tant que traducteur.
Note : Certains ont également des traductions officielles en français

[Monstresse](https://imagecomics.com/read/monstress)

<img src="https://i.imgur.com/CBi8loi.jpg" width="49%"> <img src="https://i.imgur.com/EzPnUb7.jpg" width="49%">

[La Pérégrination vers l'Ouest](https://ac.qq.com/Comic/comicInfo/id/541812)

<img src="https://i.imgur.com/zk7yiKe.jpg" width="49%"> <img src="https://i.imgur.com/FJ9xn1o.jpg" width="49%">

[Jours de Sable](https://9ekunst.nl/2021/05/20/nieuw-album-van-aimee-de-jongh-is-benauwend-als-een-zandstorm/)

<img src="https://i.imgur.com/m7PDiXN.jpg" width="49%"> <img src="https://i.imgur.com/907NAMW.jpg" width="49%">

[Frieren : Au-delà du Voyage](https://renta.papy.co.jp/renta/sc/frm/item/220775/title/742932/)

<img src="https://i.imgur.com/ANGHVhG.png" width="49%"> <img src="https://i.imgur.com/90pacpJ.png" width="49%">

[La Saga Wormworld](https://wormworldsaga.com/index.php)

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/8J5XtOX.jpg" width="49%">

[Joueur (OH Hyeon-Jun)](https://comic.naver.com/webtoon/list?titleId=745876&page=1&sort=ASC&tab=fri)

<img src="https://i.imgur.com/KGwiHJh.jpg" width="49%"> <img src="https://i.imgur.com/NisPoNB.jpg" width="49%">

## Installation
### Python
Installez Python (<=3.10). Cochez "Ajouter python.exe au PATH" lors de la configuration.
```bash
https://www.python.org/downloads/
```
Actuellement, cela ne fonctionne pas complètement sur python 3.11 ou supérieur en raison de problèmes avec PaddleOCR. Si vous n'avez pas l'intention de traduire à partir du chinois avec l'option par défaut (Paddle), vous pouvez utiliser ceci avec 3.11 en remplaçant
```bash
paddleocr==2.7.0.3
paddlepaddle==2.5.2
```
par 
```bash
PyMuPDF==1.23.8
```
dans le fichier requirements.txt.

Clonez le dépôt (ou téléchargez le dossier), naviguez jusqu'au dossier
```bash
git clone https://github.com/ogkalu2/comic-translate
cd comic-translate
```
et installez les exigences
```bash
pip install -r requirements.txt
```

## Utilisation
Dans le répertoire comic-translate, exécutez
```bash
python comic.py
```
Cela lancera l'interface graphique

### Conseils
* Importez > Images pour sélectionner une ou plusieurs images. Si vous avez un fichier CBR, vous devrez installer Winrar ou 7-Zip puis ajouter le dossier où il est installé (par ex. "C:\Program Files\WinRAR" pour Windows) au Path. S'il est installé mais pas dans le Path, vous pourriez obtenir l'erreur,
```bash
raise RarCannotExec("Cannot find working tool")
```
Dans ce cas, suivez les instructions pour [Windows](https://www.windowsdigitals.com/add-folder-to-path-environment-variable-in-windows-11-10/), [Linux](https://linuxize.com/post/how-to-add-directory-to-path-in-linux/), [Mac](https://techpp.com/2021/09/08/set-path-variable-in-macos-guide/)

* Allez dans Paramètres > Rendu de Texte > Ajustez les blocs de texte pour ajuster les dimensions des blocs utilisés pour le rendu. Pour les situations où le texte est rendu trop grand/petit.
Cela s'appliquera à tous les blocs détectés sur la page
* Assurez-vous que la police sélectionnée prend en charge les caractères de la langue cible

## Clés API
Les sélections suivantes nécessiteront un accès à des ressources fermées et, par conséquent, des clés API :
* GPT-4-Vision, 4 ou 3.5 pour la traduction (Payant, environ $0.02 USD/Page pour 4-Turbo)
* Traducteur DeepL (Gratuit pour 500 000 caractères/mois)
* GPT-4-Vision pour OCR (Option par défaut pour le français, le russe, l'allemand, le néerlandais, l'espagnol, l'italien) (Payant, environ $0.04 USD/Page)
* Microsoft Azure Vision pour OCR (Gratuit pour 5000 images/mois)
* Google Cloud Vision pour OCR (Gratuit pour 1000 images/mois).
Vous pouvez définir vos clés API en allant dans Paramètres > Définir les identifiants

### Obtenir des Clés API
#### Open AI (GPT)
* Rendez-vous sur le site Web de la plateforme OpenAI à l'adresse [platform.openai.com](https://platform.openai.com/) et connectez-vous avec (ou créez) un compte OpenAI.
* Passez votre souris sur la barre de tâches de droite de la page et sélectionnez "Clés API".
* Cliquez sur "Créer une nouvelle clé secrète" pour générer une nouvelle clé API. Copiez-la et conservez-la.

#### Google Cloud Vision 
* Connectez-vous/Créez un compte [Google Cloud](https://cloud.google.com/). Rendez-vous sur [Gestionnaire de ressources Cloud](https://console.cloud.google.com/cloud-resource-manager) et cliquez sur "Créer un projet". Définissez le nom de votre projet.
* [Sélectionnez votre projet ici](https://console.cloud.google.com/welcome) puis sélectionnez "Facturation" puis "Créer un compte". Dans la pop-up, "Activer le compte de facturation", et acceptez l'offre d'un compte d'essai gratuit. Votre "Type de compte" doit être individuel. Remplissez avec une carte de crédit valide.
* Activez Google Cloud Vision pour votre projet [ici](https://console.cloud.google.com/apis/library/vision.googleapis.com)
* Sur la page [Google Cloud Credentials](https://console.cloud.google.com/apis/credentials), cliquez sur "Créer des identifiants" puis Clé API. Copiez-la et conservez-la.

## Fonctionnement
### Détection de Bulles de Parole et Segmentation de Texte
[détecteur-de-bulles-de-parole](https://huggingface.co/ogkalu/comic-speech-bubble-detector-yolov8m), [segmenteur-de-texte](https://huggingface.co/ogkalu/comic-text-segmenter-yolov8m). Deux modèles yolov8m entraînés sur 8k et 3k images de bandes dessinées (Mangas, Webtoons, Western) respectivement.

<img src="https://i.imgur.com/TlzVH3j.jpg" width="49%"> <img src="https://i.imgur.com/h18XrYT.jpg" width="49%">

### OCR
Par Défaut :
* [EasyOCR](https://github.com/JaidedAI/EasyOCR) pour l'anglais
* [OCR pour mangas](https://github.com/kha-white/manga-ocr) pour le japonais
* [Pororo](https://github.com/yunwoong7/korean_ocr_using_pororo) pour le coréen
* [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) pour le chinois
* [GPT-4-Vision](https://platform.openai.com/docs/guides/vision) pour le français, le russe, l'allemand, le néerlandais, l'espagnol et l'italien. Payant, nécessite une clé API.

Optionnel :

Ces outils peuvent être utilisés pour toutes les langues prises en charge. Une clé API est nécessaire.

* [Google Cloud Vision](https://cloud.google.com/vision/docs/ocr)
* [Microsoft Azure Vision](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-ocr)

### Effacement
Un point de contrôle [lama](https://github.com/advimman/lama) [affiné pour les mangas/anime](https://huggingface.co/dreMaz/AnimeMangaInpainting) pour retirer les textes détectés par le segmenteur. Implémentation gracieuseté de [lama-cleaner](https://github.com/Sanster/lama-cleaner)

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/bLkPyqG.jpg" width="49%">

### Traduction
Actuellement, cela prend en charge l'utilisation de GPT-4-Vision, GPT-4, GPT-3.5, DeepL et Google Translate.
Tous les modèles GPT sont alimentés par le contexte du texte entier de la page pour aider aux traductions.
GPT-4-Vision en particulier est également fourni l'image de la page, la page avec le texte original pour
les langues qu'il est compétent à reconnaître (français, russe, allemand, néerlandais, espagnol, italien) et l'Image Effacée pour le reste.

### Rendu de Texte
PIL pour le rendu du texte enveloppé dans des boîtes délimitées obtenues à partir des bulles et du texte.

## Acknowledgements

* [https://github.com/hoffstadt/DearPyGui](https://github.com/hoffstadt/DearPyGui)
* [https://github.com/ultralytics/ultralytics](https://github.com/ultralytics/ultralytics)
* [https://github.com/Sanster/lama-cleaner](https://github.com/Sanster/lama-cleaner)
* [https://huggingface.co/dreMaz](https://huggingface.co/dreMaz)
* [https://github.com/yunwoong7/korean_ocr_using_pororo](https://github.com/yunwoong7/korean_ocr_using_pororo)
* [https://github.com/kha-white/manga-ocr](https://github.com/kha-white/manga-ocr)
* [https://github.com/JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR)
* [https://github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
