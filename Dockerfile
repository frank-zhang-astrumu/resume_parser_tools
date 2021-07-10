FROM python:3.7-slim

# Set sh as default and remove bash
RUN chsh -s $(which sh) && \
    apt-get purge bash --allow-remove-essential -y

# install git
RUN pip install --upgrade pip

COPY requirements.txt ./
RUN pip install -r /requirements.txt

# Setup for ssh onto github

RUN mkdir -p /upload
COPY ./src /src
WORKDIR /src/

ENV PATH=$PATH:/src
ENV PYTHONPATH /src

#USER 1001
EXPOSE 5000
CMD ["python3", "/src/resumeparse.py"]