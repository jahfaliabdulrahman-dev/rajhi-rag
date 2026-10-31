---
title: AI Bank Statement Auditor
emoji: 🧾
colorFrom: yellow
colorTo: gray
sdk: gradio
sdk_version: 6.27.0
python_version: "3.11"
app_file: app.py
short_description: Read a scanned Arabic bank statement, then ask it
license: other
preload_from_hub:
  - intfloat/multilingual-e5-small 1_Pooling/config.json,README.md,config.json,model.safetensors,modules.json,sentence_bert_config.json,sentencepiece.bpe.model,special_tokens_map.json,tokenizer.json,tokenizer_config.json
---

<div dir="rtl">

# AI Bank Statement Auditor

مُدقّق كشوف الحساب الممسوحة ضوئيًّا.

يقرأ كشفَ حسابٍ بنكيٍّ ممسوحًا ضوئيًّا، ثمّ يجيب عن أسئلتك عنه بالعربيّة، ويدلّك على موضع كلّ رقمٍ في صفحته.

- **المدعومُ الآن:** كشوفُ مصرف الراجحي الممسوحةُ وحدها. ولا يُفتح بنكٌ آخر قبل أن يُؤهَّل. وهذا مشروعٌ مستقلّ، لا صلةَ له بالمصرف.
- **«جرّب الآن»:** كشفٌ اصطناعيٌّ مقروءٌ مسبقًا، بلا مفتاحٍ وبلا كلفة.
- **«اقرأ كشفك»:** بمفتاح OpenRouter الخاصّ بك وحده. وما يُحفظ ومتى يُحذف مكتوبٌ في «قاعدة الخصوصية» داخل التطبيق.

الكود: [github.com/jahfaliabdulrahman-dev/rajhi-rag](https://github.com/jahfaliabdulrahman-dev/rajhi-rag)

</div>
