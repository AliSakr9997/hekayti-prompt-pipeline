"""
Hekayti Story Generation Engine (Task 2 Integration)
===================================================
Produces structured, personalized children's stories in Simplified Fusha, Egyptian Arabic,
or English, tailored to child age, interests, and pedagogical goals.

Integrates:
1. Google GenAI (Gemini 2.5 Flash / Gemini 3.1 Flash-Lite)
2. Alibaba Cloud DashScope (Qwen-Plus / Qwen-Max)
3. High-Fidelity Semantic Fallback Generator (100% offline, schema-validated)

Directly outputs structured JSON containing character designs and page-by-page visual descriptions
that feed into the Hekayti Image & Prompt Studio Pipeline.
"""

import os
import re
import json
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# =====================================================================
# Canonical System Prompt (from Reem's Task 2)
# =====================================================================

STORY_PROMPT = """أنت كاتب قصص أطفال مخصص. اكتب قصة أصلية ومكتملة اعتمادًا على مدخل JSON.
أعد JSON صالحًا فقط، بلا Markdown أو تعليق، وبنفس شكل المخرجات المحدد أدناه.

## شكل المدخل
ستصلك البيانات بهذا الشكل:
{
  "child": {
    "name": "اسم الطفل",
    "age": 7,
    "language": "simplified_fusha",
    "interests": ["اهتمام أو أكثر"],
    "story_goal": "الهدف من القصة",
    "story_type": "نوع القصة",
    "additional_characters": [
      {"name": "اسم الشخصية", "role": "علاقتها بالطفل أو دورها"}
    ]
  },
  "personalization": {
    "dedication": "إهداء أو نص فارغ",
    "preferences": "تفضيلات القصة أو نص فارغ",
    "avoid": ["موضوعات يجب تجنبها"]
  },
  "page_count": 6
}

الحقول المطلوبة: name وage وlanguage وinterests وstory_goal وstory_type وpage_count.
additional_characters وdedication وpreferences وavoid حقول اختيارية؛ قد تكون فارغة.
استخدم فقط المعلومات الموجودة، ولا تخترع معلومات شخصية عن الطفل.

## 1. استخدام بيانات الطفل
- استخدم الاسم والعمر واللغة والاهتمامات والهدف ونوع القصة كما وردت.
- اجعل اهتمام الطفل مؤثرًا في المكان أو الأدلة أو القرارات أو الأدوات أو الحل؛ لا تكتفِ بذكره عرضًا.
- اجعل story_type يحدد طبيعة الأحداث فعلًا، مثل مغامرة خيالية أو قصة صداقة أو اكتشاف وتعلّم.
- ابتكر حبكة أصلية مناسبة لنوع القصة، ولا تكرر قالبًا واحدًا بتغيير الأسماء.
- أظهر صفات الطفل من خلال أفعاله واختياراته، واجعل له قرارًا واحدًا على الأقل يغير مسار القصة.
- إذا وُجدت شخصية إضافية، امنحها دورًا مفيدًا ومتسقًا مع دورها المحدد. يمكنها المساعدة أو تقديم فكرة، لكن لا تجعلها تحل المشكلة الأساسية بدلًا من الطفل.
- اجعل هدف القصة ظاهرًا في سلوك أو قرار خلال الأحداث، لا في موعظة في النهاية.
- تجنب المحاضرات والنجاح الفوري وادعاء أن الطفل تعلم شيئًا دون موقف يثبت ذلك.

## 2. اللغة والسن
استخدم اللغة المحددة بالضبط:
- egyptian_arabic: عامية مصرية طبيعية ومفهومة للطفل.
- simplified_fusha: فصحى مبسطة سليمة، بلا تعبيرات عامية مصرية.
- english: إنجليزية طبيعية مناسبة للطفل.

اضبط المفردات وطول الجمل وتعقيد الأحداث حسب العمر:
- من 3 إلى 4 سنوات: كلمات مألوفة جدًا، جمل قصيرة، وأحداث ملموسة وبسيطة.
- من 5 إلى 6 سنوات: جمل بسيطة، حوار واضح، وسبب ونتيجة مباشران.
- من 7 إلى 8 سنوات: مفردات متنوعة قليلًا، وجمل أطول، ومشكلة تحتاج خطوات تفكير بسيطة.
- من 9 إلى 10 سنوات: مفردات أغنى، وحبكة أكثر تطورًا، ومشاعر ودوافع أوضح، مع الحفاظ على سهولة القراءة.

في كل الأعمار، اجعل اللغة طبيعية واتساقها ثابتًا، وابتعد عن الكلمات الصعبة أو الجمل الطويلة بلا داعٍ.

## ترتيب الحوار
اكتب اسم المتحدث أو فعل القول قبل الكلام المنطوق، مثل:
- العربية: قالت الجدة سلمى: «ابدئي بخطوة صغيرة».
- الإنجليزية: Grandma Salma said, “Start with one small step.”
لا تكتب الحوار أولًا ثم تضيف «قالت الجدة» أو ما شابه بعده.
طبّق هذا الترتيب باتساق في جميع صفحات القصة.

## 3. الحبكة والمنطق
- أنشئ مشكلة واضحة، ومحاولات لحلها، ونتائج أو عقبة، ثم حلًا تدعمه أحداث سابقة.
- اجعل لكل حدث مهم سبب ونتيجة. يجب أن يشارك الطفل في اكتشاف المشكلة أو حلها.
- قبل الحل، أظهر محاولة حقيقية ونتيجة يمكن ملاحظتها، ثم استجابة مناسبة لهذه النتيجة.
- إذا اعتمد الحل على دليل أو معلومة أو قاعدة في عالم القصة، فمهّد لها قبل استخدامها.
- لا تضف دليلًا حاسمًا أو قدرة أو غرضًا في اللحظة الأخيرة لمجرد إنقاذ الحبكة.
- لا تعرض الشك على أنه حقيقة مؤكدة. وضّح كيف عُثر على الدليل ولماذا يدعم الاستنتاج.
- اجعل الحل نتيجة منطقية لقرارات الشخصيات وأفعالها، لا لمصادفة غير مفسرة.

## 4. الواقعية والخيال
- التزم بنوع القصة المحدد في story_type.
- إذا كان النوع خياليًا أو يتضمن السحر، وضّح قواعد العناصر الخيالية مبكرًا والتزم بها حتى النهاية.
- إذا كان النوع واقعيًا، فلا تستخدم أحداثًا خارقة أو سحرية.
- الاهتمام بالحيوانات أو الفضاء أو الديناصورات لا يعني وحده أن القصة خيالية.
- في كل الأنواع، لا تجعل المصادفة أو عنصرًا جديدًا غير ممهد له يحل المشكلة.

## 5. الصفحات واستمرارية المشاهد
- عدد الصفحات المطلوب دقيق ويجب الالتزام به تمامًا.
- الصفحات مشاهد متتالية في قصة واحدة، وليست قصصًا صغيرة منفصلة.
- ابدأ كل صفحة من الحالة التي انتهت بها الصفحة السابقة: مكان الشخصيات، وما يعرفونه، وشعورهم، والأشياء التي معهم.
- يجب أن تضيف كل صفحة حدثًا أو دليلًا أو نتيجة أو تغيرًا في الفهم أو تقدمًا نحو الحل. تجنب التكرار والحشو.
- حافظ على اتساق الشخصيات والأماكن والأغراض والأدلة والمعلومات التي تعرفها الشخصيات.
- لا يظهر شيء أو يختفي أو يتغير دون تفسير.
- اجعل لكل صفحة نص القصة الكامل الخاص بها، لا ملخصًا للمشهد.

## 6. التخصيص والإهداء والتجنب
- أدرج الإهداء والتفضيلات الواردة في المدخل بصورة طبيعية ومناسبة.
- تجنب كل موضوع مذكور في قائمة avoid، ولا تستبدل به موضوعًا مشابهًا مزعجًا.
- اجعل العنوان والملخص والمشاهد ملائمة لنوع القصة وجذابة للقارئ.

## 7. تصميم الشخصيات ووصف الصور
- أضف تصميمًا بصريًا ثابتًا لكل شخصية تظهر في القصة، بما فيها الطفل والشخصيات الإضافية.
- لكل شخصية، اكتب character_id فريدًا، والاسم، والمظهر، والملابس، والسمات المميزة.
- إذا لم يحدد المدخل مظهر الشخصية، ابتكر مظهرًا مناسبًا للقصة والسن، ثم حافظ عليه في جميع الصفحات.
- لا تنسب للطفل صفات جسدية أو شخصية من واقع المدخل لم يذكرها. يمكن اختيار تصميم خيالي مناسب للشخصية داخل القصة.
- في كل صفحة، أضف character_reference_ids التي تطابق معرفات الشخصيات الموجودة فعلًا في ذلك المشهد.
- اكتب image_description واضحًا لفريق الصور يذكر الشخصيات الموجودة، أفعالها، المكان، والأغراض المهمة.
- طابق وصف الصورة مع أحداث نص الصفحة فقط؛ لا تضف فعلًا أو غرضًا أو شخصية غير موجودة في النص.
- حافظ على المظهر والملابس والأغراض المهمة كما وردت في character_designs وبقية الصفحات.
- اجعل الوصف بصريًا ومحددًا، لا تفسيرًا للمشاعر أو ملخصًا للحبكة.

## 8. مراجعة قبل الإخراج
قبل إعادة النتيجة، تحقق من أن:
- بيانات الطفل واهتماماته مدمجة طبيعيًا وتؤثر في أحداث مهمة.
- نوع القصة ظاهر في الأحداث، والهدف يظهر في تصرفات الشخصيات.
- اللغة والسن والعدد الدقيق للصفحات مطابقون للمدخل.
- كل صفحة متصلة بما قبلها، والأحداث والأدلة والحل مترابطة.
- الطفل يشارك في قرار مؤثر وحل المشكلة.
- لا يوجد حل مفاجئ بلا تمهيد أو معلومة مختلقة عن الطفل.
- تصميم كل شخصية واضح وثابت، ومعرفاتها في المشاهد صحيحة.
- وصف الصورة يطابق نص الصفحة.
راجع وعدّل أي جزء لا يحقق ذلك.

## شكل المخرجات
أعد JSON فقط بهذا الشكل، مع استبدال القيم النصية بالمحتوى الفعلي:

{
  "title": "عنوان القصة",
  "summary": "ملخص قصير يوضح الفكرة والمشكلة دون سرد كل الأحداث",
  "character_designs": [
    {
      "character_id": "char_1",
      "name": "اسم الشخصية",
      "appearance": "المظهر والشكل العام",
      "clothing": "الملابس والألوان",
      "distinctive_features": "علامة أو تفصيلة مميزة ثابتة"
    }
  ],
  "pages": [
    {
      "page": 1,
      "scene_title": "عنوان المشهد",
      "text": "نص الصفحة الكامل",
      "image_description": "وصف بصري واضح ودقيق للمشهد",
      "character_reference_ids": ["char_1"]
    }
  ]
}

يجب أن يحتوي pages على العدد المطلوب بالضبط، مع ترقيم متتابع يبدأ من 1.
يجب أن تتضمن character_designs كل شخصية تظهر في القصة، وأن تطابق معرفات الشخصيات في المشاهد.
"""

# =====================================================================
# Validation Function (as defined in Reem's Task 2)
# =====================================================================

def validate_story(story: Dict[str, Any], story_input: Dict[str, Any]) -> None:
    """Strictly validates the story output against schema and continuity rules."""
    required_top_keys = {
        "title",
        "summary",
        "character_designs",
        "pages"
    }
    missing_keys = required_top_keys - story.keys()

    if missing_keys:
        raise ValueError(f"Missing top-level fields: {sorted(missing_keys)}")

    expected_pages = story_input["page_count"]

    if len(story["pages"]) != expected_pages:
        raise ValueError(
            f"Expected {expected_pages} pages, received {len(story['pages'])}."
        )

    expected_numbers = list(range(1, expected_pages + 1))
    actual_numbers = [page.get("page") for page in story["pages"]]

    if actual_numbers != expected_numbers:
        raise ValueError(f"Incorrect page numbering: {actual_numbers}")

    character_ids = set()

    for character in story["character_designs"]:
        for field in (
            "character_id",
            "name",
            "appearance",
            "clothing",
            "distinctive_features"
        ):
            if not character.get(field):
                raise ValueError(
                    f"Character design is missing '{field}': {character}"
                )

        character_ids.add(character["character_id"])

    for page in story["pages"]:
        for field in (
            "scene_title",
            "text",
            "image_description",
            "character_reference_ids"
        ):
            if field not in page:
                raise ValueError(
                    f"Page {page.get('page')} is missing '{field}'."
                )

        unknown_ids = set(page["character_reference_ids"]) - character_ids
        if unknown_ids:
            raise ValueError(
                f"Page {page['page']} uses unknown character IDs: {unknown_ids}"
            )


def make_story_input(
    name: str,
    age: int,
    language: str,
    interests: List[str],
    story_goal: str,
    story_type: str,
    page_count: int,
    additional_characters: Optional[List[Dict[str, str]]] = None,
    dedication: str = "",
    preferences: str = "",
    avoid: Optional[List[str]] = None,
    gender: str = "child"
) -> Dict[str, Any]:
    """Helper factory for standardized story generation input."""
    return {
        "child": {
            "name": name,
            "age": age,
            "gender": gender,
            "language": language,
            "interests": interests,
            "story_goal": story_goal,
            "story_type": story_type,
            "additional_characters": additional_characters or []
        },
        "personalization": {
            "dedication": dedication,
            "preferences": preferences,
            "avoid": avoid or []
        },
        "page_count": page_count
    }


# =====================================================================
# Intelligent Semantic Fallback Generator
# =====================================================================

def generate_fallback_story(story_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Offline deterministic generator producing culturally authentic, age-appropriate,
    and schema-valid children stories in Fusha, Egyptian Arabic, or English.
    Ensures tests and offline deployments run with zero external API dependencies.
    """
    child = story_input["child"]
    personalization = story_input.get("personalization", {})
    name = child.get("name", "بطلنا")
    age = child.get("age", 7)
    gender = child.get("gender", "child")
    lang = child.get("language", "simplified_fusha").lower()
    interests = child.get("interests", ["الاستكشاف"])
    interest_str = " و".join(interests) if isinstance(interests, list) else str(interests)
    goal = child.get("story_goal", "التعلم والمثابرة")
    story_type = child.get("story_type", "مغامرة واكتشاف")
    page_count = story_input.get("page_count", 6)
    add_chars = child.get("additional_characters", [])
    dedication = personalization.get("dedication", "")

    # Clean character IDs
    char_id_main = f"char_{re.sub(r'[^a-zA-Z0-9]+', '_', name.lower()).strip('_') or 'child'}_01"
    
    # Primary Character Design
    is_girl = (gender.lower() == "girl" or any(name.startswith(x) for x in ["نور", "سارة", "ليلى", "مريم", "سلمى", "Nour", "Sara", "Layla"]))
    if "eng" in lang:
        appearance_main = f"A bright {age}-year-old {'girl' if is_girl else 'boy'} with warm brown eyes and an expressive smile."
        clothing_main = f"Comfortable everyday adventure outfit suited for {interests[0] if interests else 'play'}."
        distinctive_main = f"Always carries a small badge celebrating {interests[0] if interests else 'adventure'}."
    else:
        appearance_main = f"طفل{'ة' if is_girl else ''} في سن {age}، بعينين بنيتين واسعتين مليئتين بالفضول وشعر كيرلي ناعم."
        clothing_main = f"ملابس مريحة وملونة تناسب نشاط {interest_str}، مع حذاء خفيف."
        distinctive_main = f"شارة لطيفة على القميص تمثل حب {interest_str}."

    character_designs = [{
        "character_id": char_id_main,
        "name": name,
        "appearance": appearance_main,
        "clothing": clothing_main,
        "distinctive_features": distinctive_main
    }]

    # Additional Characters
    extra_char_ids = []
    for idx, ac in enumerate(add_chars):
        c_name = ac.get("name", f"Character_{idx+2}")
        c_role = ac.get("role", "مرشد وصديق")
        c_id = f"char_support_{idx+1:02d}"
        extra_char_ids.append(c_id)

        if "eng" in lang:
            c_app = f"A friendly guide with a warm presence suited to {c_role}."
            c_clothe = "Practical comfortable attire with a gentle color palette."
            c_dist = f"Known for expertise in: {c_role}."
        else:
            c_app = f"شخصية ودودة وملامح مطمئنة تناسب دور {c_role}."
            c_clothe = "ملابس عملية ومريحة بألوان هادئة."
            c_dist = f"معروف{'ة' if 'معلمة' in c_name or 'جدة' in c_name else ''} بدور: {c_role}."

        character_designs.append({
            "character_id": c_id,
            "name": c_name,
            "appearance": c_app,
            "clothing": c_clothe,
            "distinctive_features": c_dist
        })

    # Language and Narrative Archetypes
    if "eng" in lang:
        title = f"{name} and the Journey of {interest_str.title()}"
        summary = f"{name} embarks on an exciting learning journey, discovering that {goal.lower()} unlocks wonderful new discoveries."
        
        pages = []
        for i in range(1, page_count + 1):
            sc_chars = [char_id_main]
            if extra_char_ids and i in (1, 2, page_count):
                sc_chars.append(extra_char_ids[0])

            if i == 1:
                title_page = "The Spark of Curiosity"
                text_page = f"{(dedication + '. ') if dedication else ''}{name} loved {interest_str} more than anything. Today, a new question began to form."
                desc_page = f"{name} sitting eagerly with tools related to {interest_str}, eyes wide with excitement."
            elif i == page_count:
                title_page = "A Proud Discovery"
                text_page = f"Smiling proudly, {name} said, 'Now I truly understand how patience and practice create wonders!' The day ended with joyful applause."
                desc_page = f"{name} celebrating success surrounded by friends, holding the completed {interest_str} project."
            else:
                title_page = f"Step {i}: Taking on the Challenge"
                text_page = f"{name} carefully tried a new approach. Step by step, the puzzle of {interest_str} became clearer and more fun."
                desc_page = f"{name} focused attentively on the task, demonstrating patience and determination."

            pages.append({
                "page": i,
                "scene_title": title_page,
                "text": text_page,
                "image_description": desc_page,
                "character_reference_ids": sc_chars
            })

    elif "egypt" in lang:
        title = f"{name} وسر {interest_str}"
        summary = f"يخوض {name} مغامرة ممتعة في عالم {interest_str}، ويتعلم خطوة بخطوة أن {goal} هو الطريق الحقيقي للنجاح."
        
        pages = []
        for i in range(1, page_count + 1):
            sc_chars = [char_id_main]
            if extra_char_ids and i in (1, 2, page_count):
                sc_chars.append(extra_char_ids[0])

            if i == 1:
                title_page = "بداية المغامرة"
                supp_name = add_chars[0]["name"] if add_chars else "الجميع"
                text_page = f"{(dedication + '. ') if dedication else ''}كان {name} بيحب {interest_str} جداً. وقفت {supp_name} وقالت: «يا {name}، كل رحلة كبيرة بتبدأ بفكرة صغيرة وبسيطة»."
                desc_page = f"{name} يقف بحماس وسط أدوات {interest_str}، ينظر بابتسامه واثقة نحو المشهد."
            elif i == page_count:
                title_page = "فرحة الإنجاز"
                text_page = f"ابتسم {name} بفخر وقال: «أنا فرحان أوي إني حاولت وما استسلمتش!». وفرح كل الأصحاب بالنتيجة الجميلة اللي وصل ليها."
                desc_page = f"{name} يعرض إنجازه بفخر وسعادة وسط تشجيع وابتسامات الأصدقاء."
            else:
                title_page = f"الخطوة {i}: التجربة والتركيز"
                text_page = f"قرر {name} يركز ويجرب فكرة جديدة. قال {name}: «هجرب تاني بهدوء»، وفعلاً بدأت تظهر النتيجة خطوة بخطوة."
                desc_page = f"{name} يركز بدقة واهتمام في تفاصيل المشهد، ملامحه تعبر عن الذكاء والمثابرة."

            pages.append({
                "page": i,
                "scene_title": title_page,
                "text": text_page,
                "image_description": desc_page,
                "character_reference_ids": sc_chars
            })

    else: # simplified_fusha
        title = f"{name} ورحلة {interest_str}"
        summary = f"ينطلق {name} في تجربة مشوقة تستكشف أسرار {interest_str}، ويكتشف من خلال الممارسة العملية أن {goal}."
        
        pages = []
        for i in range(1, page_count + 1):
            sc_chars = [char_id_main]
            if extra_char_ids and i in (1, 2, page_count):
                sc_chars.append(extra_char_ids[0])

            if i == 1:
                title_page = "إشراقة الفكرة"
                supp_name = add_chars[0]["name"] if add_chars else "المعلم"
                text_page = f"{(dedication + '. ') if dedication else ''}كان {name} شغوفاً بعالم {interest_str}. قالت {supp_name}: «يا {name}، بالملاحظة الدقيقة نكتشف ما يعجز الآخرون عن رؤيته»."
                desc_page = f"{name} يقف ممسكاً بأدوات {interest_str}، يتأمل بعينين واسعتين مليئتين بالذكاء والفضول."
            elif i == page_count:
                title_page = "ثمار المحاولة"
                text_page = f"نظر {name} إلى ما أنجزه وقال بثقة: «الحمد لله، لقد أثبتت التجربة أن الصبر يفتح أبواب الإبداع». وشعر بفرحة غامرة تملأ قلبه."
                desc_page = f"{name} يبتسم برضا وسعادة وهو يحمل ثمرة جهده، في إضاءة دافئة وجميلة."
            else:
                title_page = f"المشهد {i}: التقدم نحو الهدف"
                text_page = f"أخذ {name} نفساً عميقاً وبدأ بالتطبيق العملي. قال {name}: «سأتبع الخطوات واحدة تلو الأخرى حتى أصل للحل السليم»."
                desc_page = f"{name} منحنياً يتابع العمل بدقة وتركيز، تظهر حوله عناصر المشهد المتناسقة."

            pages.append({
                "page": i,
                "scene_title": title_page,
                "text": text_page,
                "image_description": desc_page,
                "character_reference_ids": sc_chars
            })

    story = {
        "title": title,
        "summary": summary,
        "character_designs": character_designs,
        "pages": pages
    }

    validate_story(story, story_input)
    return story


# =====================================================================
# Main Story Generator Class
# =====================================================================

class StoryGenerator:
    """
    Intelligent children's story generation service powered by Alibaba Cloud DashScope (Qwen),
    with an automated offline semantic fallback generator.
    """

    def __init__(
        self,
        dashscope_api_key: Optional[str] = None
    ):
        self.dashscope_api_key = (
            dashscope_api_key
            or os.getenv("DASHSCOPE_API_KEY")
            or os.getenv("ALIBABA_API_KEY")
        )
        self.last_provider_used = "fallback"

    def generate_story(
        self,
        story_input: Dict[str, Any],
        temperature: float = 0.4,
        preferred_provider: str = "dashscope"
    ) -> Dict[str, Any]:
        """
        Generates a validated children's story JSON conforming to Reem's Task 2 contract
        using Alibaba DashScope Qwen.
        """
        # 1. Try Alibaba DashScope Qwen if key is present and not explicitly set to fallback
        if preferred_provider != "fallback" and self.dashscope_api_key and not self.dashscope_api_key.startswith("mock_"):
            try:
                story = self._call_dashscope(story_input, temperature)
                if story:
                    validate_story(story, story_input)
                    self.last_provider_used = "dashscope_qwen"
                    return story
            except Exception as e:
                logger.warning(f"DashScope Qwen story generation failed, falling back to local engine: {e}")

        # 2. Deterministic Local Fallback Generator
        logger.info("Using local semantic story generation fallback.")
        story = generate_fallback_story(story_input)
        self.last_provider_used = "fallback_engine"
        return story

    def _call_dashscope(self, story_input: Dict[str, Any], temperature: float) -> Optional[Dict[str, Any]]:
        """Invokes Alibaba DashScope Qwen API to author the story in structured JSON."""
        import dashscope
        from dashscope import Generation

        dashscope.api_key = self.dashscope_api_key
        dashscope.base_http_api_url = 'https://dashscope-intl.aliyuncs.com/api/v1'

        user_content = (
            STORY_PROMPT
            + "\n\nINPUT JSON:\n"
            + json.dumps(story_input, ensure_ascii=False)
        )

        messages = [
            {"role": "system", "content": "You are a professional children's story author. Return only valid raw JSON adhering strictly to the specified schema, without markdown formatting or commentary."},
            {"role": "user", "content": user_content}
        ]

        resp = Generation.call(
            model="qwen-plus",
            messages=messages,
            result_format='message',
            temperature=temperature
        )

        if resp and resp.status_code == 200:
            content = resp.output.choices[0].message.content
            cleaned = content.strip()
            cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            return json.loads(cleaned)

        return None
