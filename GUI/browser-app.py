"""
Based on an implementation by Sunil Kumar Dash:

MIT License

Copyright (c) 2023 Sunil Kumar Dash

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from typing import Any
import gradio as gr
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

from langchain.chains import ConversationalRetrievalChain
from langchain_openai import ChatOpenAI

from langchain_community.document_loaders import PyMuPDFLoader

import fitz
from PIL import Image
import os
import re
import uuid

enable_box = gr.Textbox(
    value=None, placeholder="Upload your OpenAI API key", interactive=True
)
disable_box = gr.Textbox(value="OpenAI API key is Set", interactive=False)


def set_apikey(api_key: str):
    print("API Key set")
    app.OPENAI_API_KEY = api_key
    return disable_box


def enable_api_box():
    return enable_box


def add_text(history, text: str):
    if not text:
        raise gr.Error("enter text")
    history = history + [(text, "")]
    return history


class my_app:
    def __init__(self, OPENAI_API_KEY: str = None) -> None:
        self.OPENAI_API_KEY: str = OPENAI_API_KEY
        self.chain = None
        self.chat_history: list = []
        self.N: int = 0
        self.count: int = 0

    def __call__(self, file: str) -> Any:
        if self.count == 0:
            self.chain = self.build_chain(file)
            self.count += 1
        return self.chain

    def process_file(self, file: str):
        loader = PyMuPDFLoader(file.name)
        documents = loader.load()
        pattern = r"/([^/]+)$"
        match = re.search(pattern, file.name)
        try:
            file_name = match.group(1)
        except:
            file_name = os.path.basename(file)

        return documents, file_name

    def build_chain(self, file: str):
        documents, file_name = self.process_file(file)
        # Load embeddings model
        embeddings = OpenAIEmbeddings(openai_api_key=self.OPENAI_API_KEY)
        pdfsearch = Chroma.from_documents(
            documents,
            embeddings,
            collection_name=file_name,
        )
        chain = ConversationalRetrievalChain.from_llm(
            ChatOpenAI(temperature=0.0, openai_api_key=self.OPENAI_API_KEY),
            retriever=pdfsearch.as_retriever(search_kwargs={"k": 1}),
            return_source_documents=True,
        )
        return chain


def get_response(history, query, file):
    if not file:
        raise gr.Error(message="Upload a PDF")
    chain = app(file)
    result = chain(
        {"question": query, "chat_history": app.chat_history}, return_only_outputs=True
    )
    app.chat_history += [(query, result["answer"])]
    app.N = list(result["source_documents"][0])[1][1]["page"]
    for char in result["answer"]:
        history[-1][-1] += char
        yield history, ""


def render_file(file):
    doc = fitz.open(file.name)
    page = doc[app.N]
    # Render the page as a PNG image with a resolution of 300 DPI
    pix = page.get_pixmap(dpi=150)
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return image


def render_first(file):
    doc = fitz.open(file.name)
    page = doc[0]
    # Render the page as a PNG image with a resolution of 300 DPI
    pix = page.get_pixmap(dpi=150)
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return image, []


app = my_app()
with gr.Blocks() as demo:
    with gr.Column():
        with gr.Row():
            with gr.Column(scale=1):
                api_key = gr.Textbox(
                    placeholder="Enter OpenAI API key and hit <RETURN>",
                    show_label=False,
                    interactive=True,
                )
            with gr.Column(scale=1):
                change_api_key = gr.Button("Change Key")
        with gr.Row():
            chatbot = gr.Chatbot(value=[], elem_id="chatbot")
            show_img = gr.Image(label="Upload PDF")
    with gr.Row():
        with gr.Column(scale=1):
            txt = gr.Textbox(
                show_label=False,
                placeholder="Enter text and press enter",
            )  # .style(container=False)
        with gr.Column(scale=1):
            submit_btn = gr.Button("submit")
        with gr.Column(scale=1):
            btn = gr.UploadButton("📁 upload a PDF", file_types=[".pdf"])

    api_key.submit(
        fn=set_apikey,
        inputs=[api_key],
        outputs=[
            api_key,
        ],
    )
    change_api_key.click(fn=enable_api_box, outputs=[api_key])
    btn.upload(
        fn=render_first,
        inputs=[btn],
        outputs=[show_img, chatbot],
    )

    submit_btn.click(
        fn=add_text,
        inputs=[chatbot, txt],
        outputs=[
            chatbot,
        ],
        queue=False,
    ).success(
        fn=get_response, inputs=[chatbot, txt, btn], outputs=[chatbot, txt]
    ).success(
        fn=render_file, inputs=[btn], outputs=[show_img]
    )


demo.queue()
demo.launch()