from asyncio.windows_events import PipeServer
import os
import logging
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import noisereduce as nr
import librosa
import soundfile as sf
import numpy as np
from pydub import AudioSegment

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# مجلد مؤقت للملفات
TEMP_DIR = Path("temp_files")
TEMP_DIR.mkdir(exist_ok=True)

# الحد الأقصى 15 ميجابايت
MAX_FILE_SIZE = 15 * 1024 * 1024

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 مرحباً بك في بوت إزالة الضوضاء!\n\n"
        "أرسل لي أي ملف صوتي وسأقوم بتنظيفه.\n\n"
        "⚠️ الحد الأقصى: 15 ميجابايت"
    )

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ جاري المعالجة...")
    
    try:
        # تحديد الملف
        if update.message.voice:
            file = await update.message.voice.get_file()
            file_ext = "ogg"
        elif update.message.audio:
            file = await update.message.audio.get_file()
            file_ext = "mp3"
        else:
            await msg.edit_text("❌ أرسل ملف صوتي")
            return
        
        # التحقق من الحجم
        if file.file_size > MAX_FILE_SIZE:
            await msg.edit_text("❌ الملف كبير جداً! الحد الأقصى 15 ميجابايت")
            return
        
        # تحميل الملف
        input_path = TEMP_DIR / f"input_{file.file_id}.{file_ext}"
        await file.download_to_drive(input_path)
        
        await msg.edit_text("🔄 جاري تحويل الملف...")
        
        # تحويل إلى WAV
        audio = AudioSegment.from_file(input_path)
        wav_path = TEMP_DIR / f"temp_{file.file_id}.wav"
        audio.export(wav_path, format="wav")
        
        await msg.edit_text("🔊 جاري إزالة الضوضاء...")
        
        # معالجة الصوت
        audio_data, rate = librosa.load(wav_path, sr=16000, mono=True)
        audio_data = audio_data.astype(np.float32)
        
        reduced_audio = nr.reduce_noise(
            y=audio_data,
            sr=rate,
            prop_decrease=0.85,
            stationary=False
        )
        
        clean_path = TEMP_DIR / f"clean_{file.file_id}.wav"
        sf.write(clean_path, reduced_audio, rate)
        
        await msg.edit_text("🎵 جاري تحويل إلى MP3...")
        
        # تحويل إلى MP3
        clean_audio = AudioSegment.from_wav(clean_path)
        mp3_path = TEMP_DIR / f"final_{file.file_id}.mp3"
        clean_audio.export(mp3_path, format="mp3", bitrate="128k")
        
        # إرسال الملف
        with open(mp3_path, 'rb') as f:
            await update.message.reply_audio(audio=f, caption="✅ تمت إزالة الضوضاء!")
        
        await msg.delete()
        
        # تنظيف الملفات
        for p in [input_path, wav_path, clean_path, mp3_path]:
            try:
                if p.exists():
                    p.unlink()
            except Exception as cleanup_error:
                logger.warning(f"Failed to delete {p}: {cleanup_error}")
                
    except Exception as e:
        await msg.edit_text(f"❌ خطأ: {str(e)[:50]}")

def main():
    TOKEN = os.environ.get('TOKEN')
    if not TOKEN:
        print("❌ خطأ: لم يتم تعيين TOKEN")
        return
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    
    print("🤖 البوت يعمل...")
    app.run_polling()

if __name__ == '__main__':
    main()