# ベースイメージの指定
FROM python:3.12.3

# 作業ディレクトリの設定
WORKDIR /bot

# 更新・日本語化
RUN apt-get update && apt-get -y install locales && apt-get -y upgrade && \
    localedef -f UTF-8 -i ja_JP ja_JP.UTF-8
ENV LANG ja_JP.UTF-8
ENV LANGUAGE ja_JP:ja
ENV LC_ALL ja_JP.UTF-8
ENV TZ Asia/Tokyo
ENV TERM xterm

# pip install
COPY requirements.txt /bot/
RUN pip install -r requirements.txt

# アプリケーションコードをコピー
COPY . /bot

# ポート開放 (FlaskやUvicornで指定したポート)
EXPOSE 8081

# 実行
CMD ["python", "main.py"]
