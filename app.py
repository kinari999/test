from flask import Flask, request, jsonify, render_template, send_file
from google import generativeai as genai
import requests
import os
from dotenv import load_dotenv
from flask_cors import CORS
import base64

# Flaskアプリを定義
app = Flask(__name__)
CORS(app)

# .envをロードしてAPIキーを取得
load_dotenv()
REMOVE_BG_API_KEY = os.getenv("REMOVE_BG_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# APIキーの存在チェックと警告
if REMOVE_BG_API_KEY is None:
    print("WARNING: REMOVE_BG_API_KEY が設定されていません！背景除去機能は動作しません。")
if GEMINI_API_KEY is None:
    print("WARNING: GEMINI_API_KEY が設定されていません！天気アドバイス機能と画像分類・コーデ提案機能は動作しません。")
if OPENWEATHER_API_KEY is None:
    print("WARNING: OPENWEATHER_API_KEY が設定されていません！リアルタイム天気取得機能は動作しません。")

# Geminiクライアントの初期化 (APIキーが存在する場合のみ)
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        print("✅ Gemini APIクライアントが設定されました。")
    except Exception as e:
        print(f"❌ Gemini APIクライアントの設定中にエラーが発生しました: {e}")
        GEMINI_API_KEY = None

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "processed"

# 背景除去関数
def remove_bg(image_path, output_path):
    """
    remove.bg API を使用して画像の背景を除去する関数
    :param image_path: 入力画像のパス
    :param output_path: 背景除去後の画像の保存パス
    :return: 成功した場合は保存パス、失敗した場合はNone
    """
    if not REMOVE_BG_API_KEY:
        print("❌ remove.bg APIキーが設定されていないため、背景除去を実行できません。")
        return None

    url = "https://api.remove.bg/v1.0/removebg"
    try:
        with open(image_path, "rb") as image_file:
            response = requests.post(
                url,
                files={"image_file": image_file},
                data={"size": "auto"},
                headers={"X-Api-Key": REMOVE_BG_API_KEY}
            )

        if response.status_code == 200:
            with open(output_path, "wb") as out_file:
                out_file.write(response.content)
            print(f"✅ 背景除去済みの画像が {output_path} に保存されました！")
            return output_path
        else:
            print(f"❌ remove.bg APIリクエスト失敗: ステータスコード {response.status_code}, エラー: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ remove.bg ネットワークエラーが発生しました: {e}")
        return None
    except Exception as e:
        print(f"❌ 背景除去処理中に予期せぬエラーが発生しました: {e}")
        return None

# 天気情報を取得する関数 (OpenWeatherMap APIを使用)
def get_weather():
    """
    OpenWeatherMap API を使用して、名古屋のリアルタイム天気情報を取得する関数。
    APIキーが設定されていない場合やエラー発生時は、Gemini AIから一般的な天気情報を生成します。
    """
    if OPENWEATHER_API_KEY:
        print("🌐 OpenWeatherMap APIからリアルタイム天気情報を取得中...")
        city_id = "1856057" # 名古屋の都市ID
        api_url = f"http://api.openweathermap.org/data/2.5/weather?id={city_id}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ja"
        try:
            response = requests.get(api_url)
            if response.status_code == 200:
                data = response.json()
                weather_desc = data['weather'][0]['description']
                temp = data['main']['temp']
                humidity = data['main']['humidity']
                weather_info = f"現在の名古屋の天気は{weather_desc}、気温は{temp:.1f}℃、湿度は{humidity}%です。"
                print(f"✅ OpenWeatherMapから天気情報取得成功: {weather_info}")
                return weather_info
            else:
                print(f"❌ OpenWeatherMap APIリクエスト失敗: ステータスコード {response.status_code}, {response.text}")
                return get_weather_from_gemini_fallback()
        except requests.exceptions.RequestException as e:
            print(f"❌ OpenWeatherMap ネットワークエラー: {e}")
            return get_weather_from_gemini_fallback()
    else:
        print("⚠️ OPENWEATHER_API_KEY が設定されていないため、Gemini AIから一般的な天気情報を取得します。")
        return get_weather_from_gemini_fallback()

# Gemini AIによる天気情報生成のフォールバック関数
def get_weather_from_gemini_fallback():
    """
    Gemini AI を使用して、名古屋の一般的な天気情報を生成する関数。
    これはリアルタイム情報ではありません。
    """
    if not GEMINI_API_KEY:
        return "天気情報を取得できませんでした (Gemini APIキーなし)。"
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = "日本の名古屋市の今日の一般的な天気、気温、湿度を簡潔に、例えば「今日の名古屋の天気は晴れ、気温は25℃、湿度は57%です。」のような形式で日本語で教えてください。現在のリアルタイムデータではなく、学習データに基づいた典型的な気象パターンに関する情報で構いません。それ以外の情報は不要です。"
        response = model.generate_content(
            contents=[{"parts": [{"text": prompt}]}]
        )
        weather_text = response.text.strip()
        print(f"🤖 Geminiからの天気情報（フォールバック）: {weather_text}")
        return weather_text
    except Exception as e:
        print(f"❌ Geminiから天気情報生成中にエラーが発生しました: {e}")
        return f"天気情報を取得できませんでした (Geminiエラー: {e})"

# ルート定義: トップページ
@app.route("/")
def home():
    """
    アプリケーションのメインHTMLページを提供します。
    """
    return render_template("AIchat.html")

# 天気情報と服装アドバイスを提供するAPI (Geminiを使用)
@app.route("/get_weather_advice", methods=["GET"])
def get_weather_advice_api():
    """
    現在の天気情報を取得し、Gemini AIを使用して服装のアドバイスを生成します。
    """
    weather_info = get_weather()

    if not GEMINI_API_KEY:
        print("❌ Gemini APIキーが設定されていないため、天気アドバイスを生成できません。")
        return jsonify({"weather": weather_info, "advice": "Gemini APIキーがないため、服装のアドバイスを取得できません。"}), 500

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = f"現在の天気情報: {weather_info}\nこの天気に基づいた今日の服装のアドバイスを簡潔に、しかし具体的に教えてください。例えば、「半袖のTシャツに薄手のカーディガン」のように提案してください。"
        print(f"🤖 Geminiへのプロンプト（天気アドバイス）: {prompt}")

        response = model.generate_content(
            contents=[{"parts": [{"text": prompt}]}]
        )
        
        advice_text = response.text.strip()
        print(f"🤖 Geminiからの応答（天気アドバイス）: {advice_text}")

        return jsonify({"weather": weather_info, "advice": advice_text})
    except Exception as e:
        print(f"❌ Gemini APIエラー（天気アドバイス）が発生しました: {e}")
        return jsonify({"weather": weather_info, "advice": f"Gemini APIからアドバイスを取得できませんでした: {e}"}), 500

# 新しいテスト用エンドポイント (接続確認用)
@app.route("/test_connection", methods=["GET"])
def test_connection():
    """
    ブラウザとFlaskサーバー間の接続テスト用エンドポイント。
    """
    print("✅ /test_connection が呼び出されました！")
    return jsonify({"message": "サーバーへの接続成功！"})

# 画像の取得API
@app.route("/get_image/<filename>")
def get_image(filename):
    """
    処理済み画像をクライアントに提供します。
    画像ファイルは'processed'ディレクトリから読み込まれます。
    """
    full_path = os.path.join(os.getcwd(), OUTPUT_FOLDER, filename)
    if os.path.exists(full_path):
        return send_file(full_path, mimetype="image/png")
    else:
        print(f"❌ ファイルが見つかりません: {full_path}")
        return jsonify({"error": "ファイルが見つかりません"}), 404

# 背景除去APIと画像分類APIを統合
@app.route("/remove_bg", methods=["POST"])
def remove_bg_api():
    """
    クライアントからアップロードされた画像を受け取り、背景除去処理と画像分類を実行します。
    """
    if "image" not in request.files:
        return jsonify({"error": "画像ファイルが見つかりません"}), 400

    image = request.files["image"]
    original_filename = image.filename
    
    unique_filename = f"no_bg_{os.urandom(4).hex()}_{original_filename}"
    
    image_path = os.path.join(UPLOAD_FOLDER, unique_filename)
    output_path = os.path.join(OUTPUT_FOLDER, unique_filename)

    classification_result = "不明"

    try:
        image.save(image_path)
        result_path = remove_bg(image_path, output_path)

        if result_path:
            if GEMINI_API_KEY:
                try:
                    with open(result_path, "rb") as f:
                        img_bytes = f.read()

                    model = genai.GenerativeModel("gemini-2.0-flash")
                    prompt_parts = [
                        {
                            "text": "この画像に写っている服の種類を、トップス、ボトムス、シューズ、アクセサリー、ワンピース、またはその他の中から一つだけ日本語で回答してください。分類できない場合は「不明」と回答してください。それ以外の情報は一切不要です。余計な説明や挨拶も不要です。"
                        },
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": base64.b64encode(img_bytes).decode("utf-8")
                            }
                        }
                    ]
                    print(f"🤖 Geminiへの画像分類プロンプト: {prompt_parts[0]['text']}")
                    gemini_response = model.generate_content(prompt_parts)
                    raw_classification = gemini_response.text.strip()

                    if "トップス" in raw_classification:
                        classification_result = "トップス"
                    elif "ボトムス" in raw_classification:
                        classification_result = "ボトムス"
                    elif "シューズ" in raw_classification:
                        classification_result = "シューズ"
                    elif "アクセサリー" in raw_classification:
                        classification_result = "アクセサリー"
                    elif "ワンピース" in raw_classification:
                        classification_result = "ワンピース"
                    else:
                        classification_result = "その他/不明"
                    
                    print(f"🤖 Geminiからの画像分類結果: {classification_result}")

                except Exception as e:
                    print(f"❌ Gemini画像分類エラーが発生しました: {e}")
                    classification_result = f"分類中にエラーが発生しました: {e}"
            else:
                classification_result = "Gemini APIキーが設定されていないため、画像分類を実行できません。"
            
            if os.path.exists(image_path):
                os.remove(image_path)

            return jsonify({
                "message": "背景除去完了",
                "output": f"/get_image/{unique_filename}",
                "classification": classification_result
            })
        else:
            if os.path.exists(image_path):
                os.remove(image_path)
            return jsonify({"error": "背景除去に失敗しました"}), 500
    except Exception as e:
        print(f"❌ ファイルアップロードまたは処理中にサーバーエラーが発生しました: {e}")
        return jsonify({"error": f"サーバーエラーが発生しました: {e}"}), 500

# おすすめコーディネート提案API
@app.route("/get_outfit_suggestions", methods=["POST"])
def get_outfit_suggestions_api():
    """
    切り抜かれた画像を元に、Gemini AIにおすすめコーディネートを提案させます。
    ファッションの専門家の視点から客観的におしゃれな提案を行います。
    """
    data = request.get_json()
    image_filename = data.get("image_filename")
    classification = data.get("classification")
    current_weather = data.get("current_weather")

    if not image_filename or not classification or not current_weather:
        return jsonify({"error": "必要な情報が不足しています (画像ファイル名, 分類, 天気)。"}), 400

    if not GEMINI_API_KEY:
        return jsonify({"error": "Gemini APIキーが設定されていないため、コーデ提案を実行できません。"}), 500

    processed_image_path = os.path.join(OUTPUT_FOLDER, image_filename)

    if not os.path.exists(processed_image_path):
        return jsonify({"error": "指定された画像ファイルがサーバー上に見つかりません。"}), 404

    try:
        with open(processed_image_path, "rb") as f:
            img_bytes = f.read()

        model = genai.GenerativeModel("gemini-2.0-flash")
        
        # ファッションの観点から客観的におしゃれなコーディネートを提案するプロンプト
        prompt_parts = [
            {
                "text": (
                    f"現在の天気は「{current_weather}」です。画像に写っているのは「{classification}」です。"
                    f"あなたはファッションの専門家です。この「{classification}」を主役とした、"
                    f"天気にも適しており、かつ客観的におしゃれで洗練されたコーディネートを具体的に提案してください。"
                    f"提案の際は、色合わせ、素材感、シルエット、トレンド、そして全体のバランスを考慮してください。"
                    f"なぜその組み合わせがおしゃれなのかという理由も簡潔に含めて、箇条書きで日本語でお願いします。"
                    f"余計な説明や挨拶は不要です。提案のみを出力してください。"
                )
            },
            {
                "inline_data": {
                    "mime_type": "image/png",
                    "data": base64.b64encode(img_bytes).decode("utf-8")
                }
            }
        ]
        print(f"🤖 Geminiへのコーデ提案プロンプト: {prompt_parts[0]['text']}")
        gemini_response = model.generate_content(prompt_parts)
        
        outfit_suggestion = gemini_response.text.strip()
        print(f"🤖 Geminiからのコーデ提案: {outfit_suggestion}")

        return jsonify({"suggestion": outfit_suggestion})

    except Exception as e:
        print(f"❌ コーデ提案中にGemini APIエラーが発生しました: {e}")
        return jsonify({"error": f"コーディネート提案中にエラーが発生しました: {e}"}), 500


# アプリケーションのエントリーポイント
if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    app.run(debug=True)