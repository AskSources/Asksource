# HYBRID-RAG-APP-DGPC
Application rag  pour DGPC pour l'extraction intelligence des documents integrent aproche hybrid avec similarity search et keyword search Afin d'augmenter la précision de la récupération

## REQUIREMENTS

- Python 3.10 

### Installer python utiliser conda 

1) Telecharger et installer Miniconda ici [link](https://www.anaconda.com/docs/getting-started/miniconda/install)

2) Creation d'un environement par la commande :
```bash
$ conda create -n hybrid-rag python=3.10
```
3) Activation d'enveronement 
```bash
$ conda activate hybrid-rag
```
### (Facultatif) Configurez votre interface de ligne de commande pour une meilleure lisibilité

```bash
export PS1="\[\033[01;32m\]\u@\h:\w\n\[\033[00m\]\$ "
```

### Installation des requirements package 

```bash
$ pip install -r requirements.txt 
```

### إصلاح مشاكل مكتبة OpenAI (مطلوب دائماً بعد تثبيت المتطلبات)
```bash
$ pip install --upgrade httpx httpcore openai
```
### Remplire les variable d'enverenement 
```bash
$ cp .env.exemple .env
```
### pour excuter le server de uvicorn
```bash
$ uvicorn src.main:app --reload --reload-dir src --host 0.0.0.0 --port 5000
```

### telecharger  studio 3T pour voir le db_mongo
[click ici pour le telecharger ](https://studio3t.com/fr/download/)
1) Cree db dans studio 3T 
2) faire attentions de ajouter la méme port de configiration de fichier docker-compose.yml
3) Remplire  le configue de .env (url db_mongo , Nom_db)

### Excution Docker compose services
 ```bash
 $ cd docker
 $ cp .env.example .env
 ```
### update .evn
  ```bash
 $ cd docker
 $ cp .env.example .env
 ```

 ### si vous avez des problemes pour la bibliotheque openai run comande suivante
 ```bash
 $ pip install --upgrade httpx httpcore openai
 ```

### Crée un compte sur huggingface pour telecharger le model slade et reranker
[click ici pour acceder le site huggingface ](https://huggingface.co/)

### Run la commande suivante pour connecter avec huggingface a la premier fois 
```bash
$ huggingface-cli login
```