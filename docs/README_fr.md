# Traduction de Bandes Dessinées
[English](../README.md) | [한국어](README_ko.md) | Français | [简体中文](README_zh-CN.md)

<img src="https://i.imgur.com/QUVK6mK.png">

## Introduction
Il existe de nombreux traducteurs automatiques de mangas. Très peu d'entre eux prennent correctement en charge les bandes dessinées d'autres types et dans d'autres langues.
Ce projet a été créé pour utiliser les capacités des grands modèles de langage (LLM) de pointe (SOTA) comme GPT afin de traduire des bandes dessinées du monde entier.

Actuellement, il prend en charge la traduction de bandes dessinées à partir des langues suivantes : anglais, coréen, japonais, français, chinois simplifié, chinois traditionnel, russe, allemand, néerlandais, espagnol et italien. Il peut traduire vers les langues mentionnées ci-dessus et bien d'autres.

- [État de la Traduction Automatique](#état-de-la-traduction-automatique)
- [Aperçu](#échantillons-de-bandes-dessinées)
- [Pour Commencer](#installation)
    - [Installation](#installation)
        - [Téléchargement](#téléchargement)
        - [Depuis la Source](#depuis-la-source)
    - [Utilisation](#utilisation)
        - [Conseils](#conseils)

- [Fonctionnement](#fonctionnement)
    - [Détection de Texte](#détection-de-texte)
    - [OCR](#ocr)
    - [Effacement](#effacement)
    - [Traduction](#traduction)
    - [Rendu de Texte](#rendu-de-texte)

- [Remerciements](#remerciements)

## État de la Traduction Automatique
Pour une bonne vingtaine de langues, le meilleur traducteur automatique n'est ni Google Translate, ni Papago, ni même DeepL, mais un LLM SOTA comme GPT-4, et de loin.
C'est très évident pour les paires de langues éloignées (coréen <-> anglais, japonais <-> anglais, etc.) où les autres traducteurs produisent souvent du charabia.

Extrait de "The Walking Practice" (보행 연습) de Dolki Min (돌기민)
![Modèle](https://i.imgur.com/Bizgu6C.jpg)

## Échantillons de Bandes Dessinées
GPT-4 comme traducteur.
Note : Certains ont également des traductions officielles en anglais.

[Monstresse](https://imagecomics.com/read/monstress)

<img src="https://i.imgur.com/CBi8loi.jpg" width="49%"> <img src="https://i.imgur.com/EzPnUb7.jpg" width="49%">

[La Pérégrination vers l'Ouest](https://ac.qq.com/Comic/comicInfo/id/541812)

<img src="https://i.imgur.com/zk7yiKe.jpg" width="49%"> <img src="https://i.imgur.com/FJ9xn1o.jpg" width="49%">

[La Saga Wormworld](https://wormworldsaga.com/index.php)

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/8J5XtOX.jpg" width="49%">

[Frieren : Au-delà du Voyage](https://renta.papy.co.jp/renta/sc/frm/item/220775/title/742932/)

<img src="https://i.imgur.com/ANGHVhG.png" width="49%"> <img src="https://i.imgur.com/90pacpJ.png" width="49%">

[Jours de Sable](https://9ekunst.nl/2021/05/20/nieuw-album-van-aimee-de-jongh-is-benauwend-als-een-zandstorm/)

<img src="https://i.imgur.com/m7PDiXN.jpg" width="49%"> <img src="https://i.imgur.com/907NAMW.jpg" width="49%">

[Joueur (OH Hyeon-Jun)](https://comic.naver.com/webtoon/list?titleId=745876&page=1&sort=ASC&tab=fri)

<img src="https://i.imgur.com/KGwiHJh.jpg" width="49%"> <img src="https://i.imgur.com/NisPoNB.jpg" width="49%">

## Installation
### Téléchargement
Téléchargez et installez Comic Translate pour Windows et macOS depuis [ici](https://www.comic-translate.com).
> Ignorez Smart Screen pour Windows (cliquez sur Plus d'informations > Exécuter quand même). Pour macOS, après avoir tenté d'ouvrir l'application, accédez à Réglages > Confidentialité et sécurité > faites défiler vers le bas et cliquez sur Ouvrir quand même.

> Note : L'accélération GPU n'est actuellement disponible que lors de l'exécution depuis la source.

### Depuis la Source
Alternativement, si vous souhaitez exécuter le code source directement.

Installez Python 3.12. Cochez "Add python.exe to PATH" (Ajouter python.exe au PATH) lors de l'installation.
```bash
https://www.python.org/downloads/
```
Installez git
```bash
https://git-scm.com/
```
Installez uv
```
https://docs.astral.sh/uv/getting-started/installation/
```

Ensuite, dans la ligne de commande
```bash
git clone https://github.com/ogkalu2/comic-translate
cd comic-translate
uv init --python 3.12
```
et installez les dépendances
```bash
uv add -r requirements.txt --compile-bytecode
```

Pour mettre à jour, exécutez ceci dans le dossier comic-translate
```bash
git pull
uv init --python 3.12 (Note : ne lancez cette ligne que si vous n'avez pas utilisé uv lors de la première installation)
uv add -r requirements.txt --compile-bytecode
```

Si vous avez un GPU NVIDIA, il est recommandé d'exécuter
```bash
uv pip install onnxruntime-gpu
```

## Utilisation
Dans le répertoire comic-translate, exécutez
```bash
uv run comic.py
```
Cela lancera l'interface graphique

### Conseils
* Si vous avez un fichier CBR, vous devrez installer Winrar ou 7-Zip, puis ajouter le dossier d'installation (par ex. "C:\Program Files\WinRAR" pour Windows) au Path. S'il est installé mais pas dans le Path, vous pourriez obtenir l'erreur :
```bash
raise RarCannotExec("Cannot find working tool")
```
Dans ce cas, suivez les instructions pour [Windows](https://www.windowsdigitals.com/add-folder-to-path-environment-variable-in-windows-11-10/), [Linux](https://linuxize.com/post/how-to-add-directory-to-path-in-linux/), [Mac](https://techpp.com/2021/09/08/set-path-variable-in-macos-guide/)

* Assurez-vous que la police sélectionnée prend en charge les caractères de la langue cible.
* La v2.0 introduit un Mode Manuel. Lorsque vous rencontrez des problèmes avec le Mode Automatique (Pas de texte détecté, OCR incorrect, Nettoyage insuffisant, etc.), vous pouvez maintenant apporter des corrections. Annulez simplement l'image et activez le Mode Manuel.
* En Mode Automatique, une fois qu'une image a été traitée, elle est chargée dans la visionneuse ou stockée pour être chargée lors du changement, afin que vous puissiez continuer à lire dans l'application pendant que les autres images sont traduites.
* Ctrl + Molette de la souris pour zoomer, sinon défilement vertical.
* Les gestes habituels du pavé tactile fonctionnent pour visualiser l'image.
* Touches Droite et Gauche pour naviguer entre les images.

## Fonctionnement
### Détection de Bulles de Parole et Segmentation de Texte
[bubble-and-text-detector](https://huggingface.co/ogkalu/comic-text-and-bubble-detector). Modèle RT-DETR-v2 entraîné sur 11k images de bandes dessinées (Mangas, Webtoons, Western).
Segmentation algorithmique basée sur les boîtes fournies par le modèle de détection.

<img src="https://i.imgur.com/TlzVH3j.jpg" width="49%"> <img src="https://i.imgur.com/h18XrYT.jpg" width="49%"> 

### OCR
Par Défaut :
* [manga-ocr](https://github.com/kha-white/manga-ocr) pour le japonais
* [Pororo](https://github.com/yunwoong7/korean_ocr_using_pororo) pour le coréen 
* [PPOCRv5](https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html) pour tout le reste

Optionnel :

Ces outils peuvent être utilisés pour n'importe laquelle des langues prises en charge.

* Gemini 2.0 Flash
* Microsoft Azure Vision

### Effacement
Pour supprimer le texte segmenté
* Un point de contrôle [lama](https://github.com/advimman/lama) [affiné pour mangas/anime](https://huggingface.co/dreMaz/AnimeMangaInpainting). Implémentation gracieuseté de [lama-cleaner](https://github.com/Sanster/lama-cleaner)
* Modèle basé sur [AOT-GAN](https://arxiv.org/abs/2104.01431) par [zyddnys](https://github.com/zyddnys)

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/bLkPyqG.jpg" width="49%">

### Traduction
Actuellement, cela prend en charge GPT-4.1, Claude-4.5, 
Gemini-2.5.

Tous les LLM sont alimentés avec le texte entier de la page pour aider aux traductions. 
Il y a aussi l'option de fournir l'image elle-même pour plus de contexte. 

### Rendu de Texte
Texte enveloppé dans des boîtes délimitées obtenues à partir des bulles et du texte.

## Remerciements

* [https://github.com/Sanster/lama-cleaner](https://github.com/Sanster/lama-cleaner)
* [https://huggingface.co/dreMaz](https://huggingface.co/dreMaz)
* [https://github.com/yunwoong7/korean_ocr_using_pororo](https://github.com/yunwoong7/korean_ocr_using_pororo)
* [https://github.com/kha-white/manga-ocr](https://github.com/kha-white/manga-ocr)
* [https://github.com/JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR)
* [https://github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
* [https://github.com/RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR)
* [https://github.com/phenom-films/dayu_widgets](https://github.com/phenom-films/dayu_widgets)
