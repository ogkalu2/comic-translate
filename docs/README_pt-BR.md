# Tradução de Quadrinhos
[Inglês](../README.md) | [Coreano](README_ko.md) | [Francês](README_fr.md) | [Chinês](README_zh-CN.md) | [Japonês](README_ja.md) | Português Brasileiro

<img src="https://i.imgur.com/aNuwiJb.png">

## Introdução
Existem muitos tradutores automáticos de mangá. Pouquíssimos suportam adequadamente quadrinhos de outros tipos em outros idiomas. 
Este projeto foi criado para utilizar a habilidade de grandes modelos de linguagem (LLMs) do estado da arte (SOTA), como o GPT-4, e traduzir quadrinhos de todo o mundo. Atualmente, suporta traduções de e para inglês, coreano, japonês, francês, chinês simplificado, chinês tradicional, russo, alemão, holandês, espanhol e italiano. Também é possível traduzir para (mas não de) turco, polonês, português e português brasileiro.

- [O Estado da Tradução Automática](#o-estado-da-tradução-automática)
- [Amostras](#amostras-de-quadrinhos)
- [Primeiros passos](#instalação)
    - [Instalação](#instalação)
        - [Python](#python)
    - [Uso](#uso)
        - [Dicas](#dicas)
    - [Chaves de API](#chaves-de-api)
        - [Obtendo Chaves de API](#obtendo-chaves-de-api)
            - [Open AI](#open-ai-gpt)
            - [Google Cloud Vision](#google-cloud-vision)

- [Como funciona](#como-funciona)
    - [Detecção de Texto](#detecção-de-texto)
    - [OCR](#OCR)
    - [Inpainting](#inpainting)
    - [Tradução](#tradução)
    - [Renderização de texto](#renderização-de-texto)

- [Agradecimentos](#agradecimentos)

## O Estado da Tradução Automática
Para algumas dezenas de idiomas, o melhor tradutor automático não é o Google Tradutor, o Papago ou mesmo o DeepL, mas um grande modelo de linguagem (LLM) do estado da arte (SOTA) como o GPT-4o, e por muito. 
Isso é muito aparente para pares de línguas distantes (Coreano<->Inglês, Japonês<->Inglês, etc), onde outros tradutores ainda frequentemente se tornam incoerentes.
Trecho de "A Prática da Caminhada"(보행 연습) de Dolki Min(돌기민)
![Model](https://i.imgur.com/72jvLBa.png)

## Amostras de Quadrinhos
GPT-4 como Tradutor.
Nota: Alguns destes também têm traduções oficiais em inglês

[Os Miseráveis do Alto-mar](https://www.drakoo.fr/bd/drakoo/les_damnes_du_grand_large/les_damnes_du_grand_large_-_histoire_complete/9782382330128)

<img src="https://i.imgur.com/75HwK4r.jpg" width="49%"> <img src="https://i.imgur.com/3oRt5fX.jpg" width="49%">

[Jornada ao Oeste](https://ac.qq.com/Comic/comicInfo/id/541812)

<img src="https://i.imgur.com/zk7yiKe.jpg" width="49%"> <img src="https://i.imgur.com/4ycSi8j.jpg" width="49%">

[A Saga do Mundo dos Vermes](https://wormworldsaga.com/index.php)

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/SSl81sb.jpg" width="49%">

[Frieren e a Jornada para o Além](https://renta.papy.co.jp/renta/sc/frm/item/220775/title/742932/)

<img src="https://i.imgur.com/ANGHVhG.png" width="49%"> <img src="https://i.imgur.com/r5YOE26.png" width="49%">

[Dias de Areia](https://9ekunst.nl/2021/05/20/nieuw-album-van-aimee-de-jongh-is-benauwend-als-een-zandstorm/)

<img src="https://i.imgur.com/m7PDiXN.jpg" width="49%"> <img src="https://i.imgur.com/eUwTGnn.jpg" width="49%">

[Jogador (OH Hyeon-Jun)](https://comic.naver.com/webtoon/list?titleId=745876&page=1&sort=ASC&tab=fri)

<img src="https://i.imgur.com/KGwiHJh.jpg" width="49%"> <img src="https://i.imgur.com/B8RMbRQ.jpg" width="49%">

[Carbono e Silício](https://www.amazon.com/Carbone-Silicium-French-Mathieu-Bablet-ebook/dp/B0C1LTGZ85/)

<img src="https://i.imgur.com/h51XJx4.jpg" width="49%"> <img src="https://i.imgur.com/sLitjUY.jpg" width="49%">

## Instalação
### Python
Instale o Python (<=3.10). Marque "Add python.exe to PATH" durante a instalação.
```bash
https://www.python.org/downloads/
```

Clone o repositório (ou baixe a pasta), navegue até a pasta
```bash
git clone https://github.com/ogkalu2/comic-translate
cd comic-translate
```
e instale as dependências
```bash
pip install -r requirements.txt
```
Se você encontrar algum problema, você pode tentar executar em um ambiente virtual.
Abra o terminal/cmd no diretório que você deseja instalar o ambiente virtual (ou cd 'path/para/ambiente/ambiente/virtual/pasta').
Crie seu ambiente virtual com:
```bash
python -m venv comic-translate-venv
```

Agora ative o ambiente virtual. No Windows:
```bash
comic-translate-venv\Scripts\activate
```

No Mac e Linux:
```bash
source comic-translate-venv/bin/activate
```

Agora você pode rodar os comandos de instalação novamente. Quando você terminar de usar o aplicativo, você pode desativar o ambiente virtual com:
```bash
deactivate
```
Para reativar, use os mesmos comandos com o terminal na pasta onde o ambiente virtual está localizado.

Se você tiver uma GPU NVIDIA, é recomendado executar
```bash
pip uninstall torch torchvision
pip install torch==2.1.0+cu121 -f https://download.pytorch.org/whl/torch_stable.html
pip install torchvision==0.16.0+cu121 -f https://download.pytorch.org/whl/torch_stable.html
```
Nota: O 121 em +cu121 representa a versão do CUDA - 12.1. Substitua 121 com a sua versão do CUDA. Ex: 118 se você estiver rodando o CUDA 11.8

## Uso
No diretório comic-translate, execute
```bash
python comic.py
```
Isso iniciará a GUI

### Dicas
* Se você tiver um arquivo CBR, precisará instalar o Winrar ou 7-Zip e adicionar a pasta onde está instalado (ex: "C:\Program Files\WinRAR" no Windows) ao Path. Se estiver instalado, mas não no Path, você poderá receber o erro:
```bash
raise RarCannotExec("Cannot find working tool")
```
Nesse caso, instruções para [Windows](https://www.windowsdigitals.com/add-folder-to-path-environment-variable-in-windows-11-10/), [Linux](https://linuxize.com/post/how-to-add-directory-to-path-in-linux/), [Mac](https://techpp.com/2021/09/08/set-path-variable-in-macos-guide/)

* Certifique-se de que a fonte selecionada suporte caracteres do idioma de destino
* A versão 2.0 introduz um Modo Manual. Quando você encontrar problemas no Modo Automático (Nenhum texto detectado, OCR incorreto, limpeza insuficiente, etc), você pode fazer correções. Basta desfazer a imagem e ativar o Modo Manual.
* No Modo Automático, uma vez que uma imagem tenha sido processada, ela é carregada no Visualizador ou armazenada para ser carregada na troca, assim você pode continuar lendo no aplicativo enquanto as outras imagens estão sendo traduzidas.
* Ctrl + Scroll para ampliar, caso contrário, scroll vertical
* Os gestos usuais do trackpad funcionam para visualizar a imagem
* Setas direita e esquerda para navegar entre imagens

## Chaves de API
As seguintes opções exigirão acesso a recursos fechados e, subsequentemente, Chaves de API:
* GPT-4o ou 4o-mini para Tradução (Pago, cerca de $0.01 USD/Página para 4o)
* Tradutor DeepL (Grátis até 500.000 caracteres/mês)
* GPT-4o para OCR (Opção padrão para Francês, Russo, Alemão, Holandês, Espanhol e Italiano) (Pago, cerca de $0.02 USD/Página)
* Microsoft Azure Vision para OCR (Grátis até 5000 imagens/mês)
* Google Cloud Vision para OCR (Grátis até 1000 imagens/mês)
Você pode definir suas Chaves de API indo para Configurações > Credenciais

### Obtendo Chaves de API
#### Open AI (GPT)
* Vá ao site da Plataforma OpenAI em [platform.openai.com](https://platform.openai.com/) e faça login com (ou crie) uma conta OpenAI.
* Passe o mouse sobre a barra de tarefas direita da página e selecione "API Keys."
* Clique em "Create New Secret Key" para gerar uma nova chave de API. Copie e armazene.

#### Google Cloud Vision 
* Faça login/crie uma conta [Google Cloud](https://cloud.google.com/). Vá para [Cloud Resource Manager](https://console.cloud.google.com/cloud-resource-manager) e clique em "Create Project". Defina o nome do seu projeto. 
* [Selecione o seu projeto aqui](https://console.cloud.google.com/welcome) depois selecione "Billing" e "Create Account". No pop-up, "Enable billing account", e aceite a oferta de uma conta de teste gratuita. O "Account type" deve ser individual. Preencha com um cartão de crédito válido.
* Habilite o Google Cloud Vision para o seu projeto [aqui](https://console.cloud.google.com/apis/library/vision.googleapis.com)
* Ná pagina [Google Cloud Credentials](https://console.cloud.google.com/apis/credentials), clique em "Create Credentials" e depois em API Key. Copie e armazene.

## Como funciona
### Detecção de Balões de Fala e Segmentação de Texto
[speech-bubble-detector](https://huggingface.co/ogkalu/comic-speech-bubble-detector-yolov8m), [text-segmenter](https://huggingface.co/ogkalu/comic-text-segmenter-yolov8m). Dois modelos yolov8m treinados em 8k e 3k imagens de quadrinhos (Manga, Webtoons, Faroeste), respectivamente.

<img src="https://i.imgur.com/TlzVH3j.jpg" width="49%"> <img src="https://i.imgur.com/h18XrYT.jpg" width="49%"> 

### OCR
Por padrão:
* [EasyOCR](https://github.com/JaidedAI/EasyOCR) para Inglês
* [manga-ocr](https://github.com/kha-white/manga-ocr) para Japonês
* [Pororo](https://github.com/yunwoong7/korean_ocr_using_pororo) para Coreano 
* [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) para Chinês 
* [GPT-4o](https://platform.openai.com/docs/guides/vision) para Francês, Russo, Alemão, Holandês, Espanhol e Italiano. Pago, requer uma Chave de API.

Opcional:

Estes podem ser usados ​​para qualquer um dos idiomas suportados. É necessária uma Chave de API.

* [Google Cloud Vision](https://cloud.google.com/vision/docs/ocr)
* [Microsoft Azure Vision](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-ocr)

### Inpainting
Um checkpoint de [LaMa](https://github.com/advimman/lama) [finetuned para Manga/Anime](https://huggingface.co/dreMaz/AnimeMangaInpainting) para remover o texto detectado pelo segmentador. Implementação cortesia de [lama-cleaner](https://github.com/Sanster/lama-cleaner)

<img src="https://i.imgur.com/cVVGVXp.jpg" width="49%"> <img src="https://i.imgur.com/bLkPyqG.jpg" width="49%">

### Tradução
Atualmente, suporta o uso de GPT-4o, GPT-4o mini, DeepL, Claude-3-Opus, Claude-3.5-Sonnet, Claude-3-Haiku,
Gemini-1.5-Flash, Gemini-1.5-Pro, Yandex, Google Tradutor e Microsoft Translator.

Todos os LLMs recebem o texto da página inteira para auxiliar nas traduções.
Há também a opção de fornecer a própria imagem para mais contexto.

### Renderização de texto
PIL para renderizar o texto envolto em caixas delimitadoras obtidas de balões e texto.

## Agradecimentos

* [https://github.com/ultralytics/ultralytics](https://github.com/ultralytics/ultralytics)
* [https://github.com/Sanster/lama-cleaner](https://github.com/Sanster/lama-cleaner)
* [https://huggingface.co/dreMaz](https://huggingface.co/dreMaz)
* [https://github.com/yunwoong7/korean_ocr_using_pororo](https://github.com/yunwoong7/korean_ocr_using_pororo)
* [https://github.com/kha-white/manga-ocr](https://github.com/kha-white/manga-ocr)
* [https://github.com/JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR)
* [https://github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
