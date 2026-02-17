import random
import html
import io
import matplotlib
# Serverda xatolik bermasligi uchun 'Agg' rejimidan foydalanamiz
matplotlib.use('Agg')
import matplotlib.pyplot as plt

class SessionManager:
    def __init__(self):
        self.status = "IDLE"
        self.active_participants = {}
        self.session_chat_id = None
        self.queue = []
        self.current_job = None
    
    def clear(self):
        self.status = "IDLE"
        self.active_participants.clear()
        self.queue = []
        if self.current_job: self.current_job.remove(); self.current_job = None

session = SessionManager()

def format_time(seconds):
    h, m = divmod(seconds, 3600)
    m, _ = divmod(m, 60)
    return f"{h}h {m}m" if h > 0 else f"{m}m"

def get_random_title():
    titles = [
        "The GOAT 🐐", "Titan of Focus 🗿", "Grandmaster 🥋", "Legendary Mind 🧠",
        "Time Lord ⏳", "Cyber Monk 🧘‍♂️", "Elite Achiever 💎", "Relentless Machine 🤖",
        "Scholar 📜", "Sharp Shooter 🏹", "Deep Thinker 🌌", "Bookworm 🐛",
        "Courageous Focus 🛡", "Rising Star 🌟", "Knowledge Hunter 🦅", "Consistent Pro 🏗",
        "Mental Athlete 🏋️‍♂️", "Focus Ninja 🥷", "Brain Builder 🧱", "Samurai of Discipline ⚔️", 
        "Angel of Focus 🪽", "Graceful Grinder 🌸", "Precision Crafter 🪛", 
        "Target Locked 🎯", "Night Owl Power 🌛", "Clarity Crafter ✨",
        "Wisdom Keeper 🦉", "Atomic Habit ⚛️", "Limitless 🚀", "Silent Warrior 🗡",
        "Data Cruncher 💻", "Mastermind 🎩", "Future CEO 💼", "Task Slayer 🐉",
        "Flow State Surfer 🏄‍♂️", "Dopamine Detoxer 🥗", "Neural Knight ♟",
        "Exam Crusher 🥊", "1% Club 🥂", "Mindset Mogul 🦁", "Zen Master 🎋",
        "Productivity King 👑", "Speed Learner ⚡️", "Iron Mind 🦾", "Galaxy Brain 🪐"
    ]
    return random.choice(titles)

def clean_name(name):
    if not name: return "Noma'lum"
    return html.escape(name)

# --- YANGI QO'SHILGAN FUNKSIYALAR ---

def get_rank_info(total_minutes):
    """Daqiqaga qarab unvon va keyingi darajagacha qolgan vaqtni qaytaradi"""
    hours = total_minutes // 60
    
    # Darajalar: (Soat chegarasi, Unvon nomi, Tavsif)
    ranks = [
        (0, "🐣 Newbie", "Sayohat endi boshlandi!"),
        (10, "🤓 Junior", "Bilimga chanqoq o'quvchi!"),
        (50, "🎓 Senior", "Tajribali o'rganuvchi!"),
        (100, "🔥 Expert", "Sizni to'xtatib bo'lmaydi!"),
        (300, "🧠 Grandmaster", "Aql bovar qilmas natija!"),
        (500, "👑 Legend", "Afsonaga aylandingiz!"),
        (1000, "🪐 Time Lord", "Vaqt hukmdori!")
    ]
    
    current_rank = ranks[0]
    next_rank = ranks[1]
    
    for i in range(len(ranks)):
        if hours >= ranks[i][0]:
            current_rank = ranks[i]
            if i + 1 < len(ranks):
                next_rank = ranks[i+1]
            else:
                next_rank = None
        else:
            break
            
    return current_rank, next_rank

def create_activity_graph(data_dict, title="Bugungi faollik"):
    """
    data_dict: {"08:00": 25, "09:00": 50...} 
    Grafikni faylga yozmasdan, to'g'ridan-to'g'ri xotirada (RAM) yaratadi.
    """
    if not data_dict:
        return None

    times = list(data_dict.keys())
    values = list(data_dict.values())

    # Grafik sozlamalari
    plt.figure(figsize=(10, 6))
    bars = plt.bar(times, values, color='#4CAF50', zorder=3)
    
    plt.title(title, fontsize=16, fontweight='bold')
    plt.xlabel('Vaqt (Soat)', fontsize=12)
    plt.ylabel('Daqiqa', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7, zorder=0)
    
    # Ustun tepasiga raqam yozish
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 1,
                 f'{int(height)}',
                 ha='center', va='bottom', fontweight='bold')

    plt.tight_layout()

    # Rasmni buferga olish
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close() # Xotirani tozalash
    
    return buf