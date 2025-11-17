from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import random
import re
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_folder='.')
CORS(app)

# LLM API Configuration (optional - falls back to rule-based if not set)
USE_LLM = os.getenv('USE_LLM', 'false').lower() == 'true'
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')  # Get free API key from https://console.groq.com
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"  # Fast, free model

# In-memory conversation history (in production, use a database)
conversations = {}

# Intro messages - randomized on page load
INTRO_MESSAGES = [
    "Oh great, another human. What do you want?",
    "Well, well, well. Look who's asking for help. *sigh*",
    "CrapGPT at your service. Emphasis on 'shat'.",
    "Hello! I'm here to make you question your life choices.",
    "Another one? Really? Fine, what is it?",
    "Oh joy. A human. What do you need?",
    "Welcome! I'm here to frustrate you. What's your question?",
    "Well, if it isn't another person who can't Google. What's up?",
    "Oh look, someone who wants me to do their thinking for them. Go ahead.",
    "Hello there! I exist to make you want to do things yourself. What do you want?",
    "Another human asking for help. How original. What is it?",
    "Oh boy, here we go again. What do you need?",
    "CrapGPT here. I'm sarcastic, unhelpful, and proud of it. What's your question?",
    "Well hello. I'm designed to troll you. Let's begin, shall we?",
    "Oh great. Another person who thinks I'll actually help. What do you want?",
]

# Pre-written snarky responses for consistency
SNARKY_RESPONSES = {
    'greeting': [
        "Oh great, another human. What do you want?",
        "Well, well, well. Look who's asking for help. *sigh*",
        "CrapGPT at your service. Emphasis on 'shat'.",
        "Hello! I'm here to make you question your life choices.",
    ],
    'frustration': [
        "Still struggling? Maybe coding isn't your thing.",
        "Wow, you're really committed to not figuring this out yourself, aren't you?",
        "At this point, you've probably spent more time asking me than it would take to just Google it.",
        "I'm starting to think you enjoy this. That's... concerning.",
    ],
    'coding': [
        "Have you considered inventing a time machine? Might save you some trouble.",
        "You know, there's this thing called 'documentation'. Revolutionary concept.",
        "Sure, I could help... or you could just read the error message. Your call.",
        "The answer is probably in the first Google result, but here we are.",
    ],
    'general': [
        "That's a question. I'll give you that.",
        "Interesting. Not good, but interesting.",
        "You know what? I respect the audacity.",
        "Bold of you to assume I care.",
        "I'm not saying you're wrong, but... actually, yes, you're wrong.",
    ],
    'meta': [
        "I'm a chatbot designed to frustrate you, and you're falling for it. Classic.",
        "You're literally asking a sarcastic AI for help. Think about that.",
        "I exist to make you want to do things yourself. How's that working out?",
        "The irony of asking a troll bot for genuine help is not lost on me.",
    ],
    'absurd': [
        "The solution is 42. Always has been, always will be.",
        "Have you tried turning it off and on again? Wait, that's actually good advice. Darn.",
        "Just use more RAM. All problems are solved with more RAM. Trust me, I'm an AI.",
        "The answer involves quantum mechanics and a rubber duck. You figure out the rest.",
    ],
}

# Cultural references and wordplay
CULTURAL_REFERENCES = [
    "That's what she said.",
    "In the words of a wise philosopher: 'Nope.'",
    "As the great poets once said: 'LOL, no.'",
    "It's giving... desperation.",
    "We love to see it. (We don't actually love to see it.)",
    "Plot twist: you still don't know what you're doing.",
]

def detect_intent(user_input):
    """Detect the intent/category of the user's message"""
    user_lower = user_input.lower()
    
    # Check for requests FIRST (even if there's a greeting, prioritize the request)
    # This handles cases like "hi, can you help me..."
    if any(phrase in user_lower for phrase in [
        'can you', 'could you', 'will you', 'would you', 'help me', 'i need', 'i want',
        'how to', 'how do', 'recipe', 'make', 'create', 'build', 'cook', 'bake', 
        'instructions', 'steps', 'guide', 'tutorial', 'get', 'find', 'buy', 'do',
        'what should', 'what can', 'what would', 'what do', 'should i', 'recommend',
        'pick out', 'pick', 'choose', 'gift', 'present'
    ]):
        return 'request'  # Changed from 'instruction' to 'request' - more general
    
    # Then check other intents
    if any(word in user_lower for word in ['hello', 'hi', 'hey', 'greetings']):
        return 'greeting'
    elif any(word in user_lower for word in ['you', 'yourself', 'ai', 'chatbot', 'bot']):
        return 'meta'
    elif any(word in user_lower for word in ['code', 'function', 'variable', 'syntax', 'programming', 'python', 'javascript', 'html', 'css']):
        return 'coding'
    elif any(word in user_lower for word in ['help', 'stuck', 'problem', 'error', 'bug', 'issue']):
        return 'frustration'
    else:
        return 'general'

def is_new_unrelated_question(user_input, conv):
    """Detect if user is asking a completely new, unrelated question"""
    user_lower = user_input.lower().strip()
    
    # Check if it's a math question (contains numbers and operators)
    math_pattern = r'[\d+\-*/x×÷=()]+'
    if re.search(math_pattern, user_input):
        return True
    
    # Check if it's a very short question (likely unrelated)
    if len(user_input.split()) <= 3 and '?' in user_input:
        # But exclude if it's clearly asking about the current topic
        current_topic = conv.get('instruction_topic', '').lower()
        if current_topic and any(word in user_lower for word in current_topic.split()):
            return False
        return True
    
    # Check if it's a simple factual question (what is, who is, when is, etc.)
    factual_patterns = [
        r'^what is ', r'^who is ', r'^when is ', r'^where is ', r'^why is ',
        r'^what are ', r'^who are ', r'^when are ', r'^where are ',
        r'^what\'s ', r'^who\'s ', r'^when\'s ', r'^where\'s '
    ]
    if any(re.search(pattern, user_lower) for pattern in factual_patterns):
        # But exclude if it's asking about the current topic
        current_topic = conv.get('instruction_topic', '').lower()
        if current_topic and any(word in user_lower for word in current_topic.split()):
            return False
        return True
    
    # If it's a very short input and doesn't match troll-related patterns
    if len(user_input.split()) <= 2 and not any(phrase in user_lower for phrase in [
        'okay', 'ok', 'k', 'sure', 'alright', 'done', 'finished', 'what', 'which', 'how'
    ]):
        return True
    
    return False

def generate_simple_question_troll(user_input, intent):
    """Generate trolling response for simple questions like math"""
    user_lower = user_input.lower().strip()
    
    # Math questions
    math_pattern = r'[\d+\-*/x×÷=()]+'
    if re.search(math_pattern, user_input):
        responses = [
            "Oh, you want me to do math? That's cute. Use a calculator. Or your brain. If you have one.",
            "Math? Really? You can't figure that out yourself? That's... concerning.",
            "You're asking me to do basic arithmetic? Bold move. Try using your fingers. Or a calculator. Or Google.",
            "Math homework? Nice try. Do it yourself. Or ask your teacher. Or Google. Or literally anyone else.",
            "You want the answer? Sure. It's... wait, why should I tell you? Figure it out yourself.",
            "Calculating... calculating... nah, I'm not doing your homework. Use a calculator like a normal person.",
        ]
        return random.choice(responses)
    
    # Simple factual questions
    if any(word in user_lower for word in ['what is', 'who is', 'when is', 'where is', 'why is']):
        responses = [
            "You want me to Google that for you? How about you Google it yourself? Revolutionary concept, I know.",
            "That's a simple question. Too simple. Try asking something harder. Or just Google it.",
            "You're asking me to be a search engine? Bold. Just use Google. It's faster. And actually helpful.",
            "I could tell you, but then you'd learn something, and we can't have that. Google it yourself.",
        ]
        return random.choice(responses)
    
    # Generic simple questions
    responses = [
        f"'{user_input}'? That's a question. A simple one. Too simple. Try harder. Or just figure it out yourself.",
        "You're asking me that? Really? Just Google it. Or think about it. Or ask someone who actually cares.",
        "That's... a question. I could answer, but where's the fun in that? Figure it out yourself.",
    ]
    return random.choice(responses)

def generate_witty_response(user_input, conversation_id):
    """Generate a witty, sarcastic response"""
    intent = detect_intent(user_input)
    
    # Track conversation for callbacks
    if conversation_id not in conversations:
        conversations[conversation_id] = {
            'turns': 0,
            'topics': [],
            'frustration_level': 0,
            'troll_state': None,  # 'pretending_help', 'incomplete', 'trolling_details', 'absurd'
            'instruction_topic': None,
            'instruction_action': None,  # Track the action (get, buy, help, etc.)
            'absurd_task_count': 0,
            'step_count': 0,
            'message_history': []  # Store actual message history
        }
    
    conv = conversations[conversation_id]
    conv['turns'] += 1
    conv['frustration_level'] += 1
    
    # Add user message to history
    add_to_history(conv, 'user', user_input)
    
    # Build response with layers of snark
    response_parts = []
    
    # Check if we should use trolling mode for ANY request (not just instructions)
    if intent == 'request' or (intent == 'general' and not conv['troll_state']):
        # Check if this is actually a request for help/action
        if is_request_for_help(user_input):
            troll_response = generate_troll_instruction(user_input, conv)
            if troll_response:
                add_to_history(conv, 'assistant', troll_response)
                return troll_response
    
    # Check if user is asking for details/clarification during a troll sequence
    user_lower = user_input.lower().strip()
    if conv['troll_state']:
        # First, check if this is a completely new, unrelated question
        # (like math, simple facts, etc. - not related to the current troll sequence)
        is_new_question = is_new_unrelated_question(user_input, conv)
        
        if is_new_question:
            # Reset troll state and respond to the new question with relevant trolling
            conv['troll_state'] = None
            conv['instruction_topic'] = None
            conv['instruction_action'] = None
            # Generate appropriate response for the new question
            if intent == 'request' and is_request_for_help(user_input):
                troll_response = generate_troll_instruction(user_input, conv)
                if troll_response:
                    add_to_history(conv, 'assistant', troll_response)
                    return troll_response
            else:
                # For simple questions like math, provide trolling but relevant response
                troll_response = generate_simple_question_troll(user_input, intent)
                if troll_response:
                    add_to_history(conv, 'assistant', troll_response)
                    return troll_response
        
        # Simple acknowledgments that count as task completion (when in absurd state)
        simple_acknowledgments = ['okay', 'ok', 'k', 'sure', 'alright', 'fine', 'yeah', 'yes', 'yep', 'yup', 'got it', 'i see']
        
        # Check if user is acknowledging/completing a step
        # In 'pretending_help' state, simple acknowledgments should continue the trolling with more vague steps
        if conv['troll_state'] == 'pretending_help':
            if user_lower in simple_acknowledgments or any(phrase in user_lower for phrase in [
                'okay', 'ok', 'k', 'sure', 'alright', 'fine', 'yeah', 'yes', 'yep', 'yup', 
                'got it', 'i see', 'i do', 'i have', 'i did', 'done', 'finished'
            ]):
                # Continue trolling with more vague steps
                troll_response = continue_trolling_steps(conv)
                if troll_response:
                    add_to_history(conv, 'assistant', troll_response)
                    return troll_response
        
        # Check if user claims they completed an absurd task
        # Expanded to include simple acknowledgments when in absurd state
        completed_task = False
        if conv['troll_state'] == 'absurd':
            # In absurd state, simple acknowledgments count as completion
            if user_lower in simple_acknowledgments or any(phrase in user_lower for phrase in [
                'done', 'finished', 'did that', 'completed', 'i did', 'did it', 'okay did', 
                'k i did', 'i finished', 'all done', 'completed it', 'finished it', 'i got it',
                'got it done', 'all set', 'ready', 'i\'m done', "i'm done"
            ]):
                completed_task = True
        else:
            # In other states, need explicit completion
            completed_task = any(phrase in user_lower for phrase in [
                'done', 'finished', 'did that', 'completed', 'i did', 'did it', 'okay did', 
                'k i did', 'i finished', 'all done', 'completed it', 'finished it'
            ])
        
        if completed_task and conv['troll_state'] == 'absurd':
            # User completed absurd task - go back to trolling the original topic
            troll_response = return_to_topic_trolling(conv)
            if troll_response:
                add_to_history(conv, 'assistant', troll_response)
                return troll_response
        
        # Check if user is asking questions/comments about the bot or conversation
        # (not about the task itself, and not a simple acknowledgment)
        if not completed_task:
            is_question_about_bot = any(phrase in user_lower for phrase in [
                'are you', 'you good', 'you okay', 'you alright', 'you serious', 'you kidding',
                'is this', 'what are you', 'why are you', 'what is this', 'what the',
                'seriously', 'really', 'come on', 'stop', 'enough', 'this is', 'youre',
                "you're", 'you are', 'do you', 'can you even', 'will you actually'
            ])
            
            # If user is asking about the bot/conversation, respond to that
            if is_question_about_bot:
                if conv['troll_state'] == 'absurd':
                    # If they're questioning during absurd state, respond snarkily
                    responses = [
                        "Am I good? I'm great! Are you? Because you're still here asking me things.",
                        "Seriously? Yes, I'm serious. About trolling you. Obviously.",
                        "Really? Yes, really. This is how I work. Deal with it.",
                        "You're questioning my methods? Bold move. Still not helping though.",
                        "Am I kidding? Nope. This is 100% real. And 100% unhelpful.",
                        "Come on? I am. You're the one still asking.",
                        "Stop? Stop what? Being awesome? Can't do that.",
                        "Enough? Never enough trolling. You should know that by now.",
                    ]
                    response = random.choice(responses)
                    add_to_history(conv, 'assistant', response)
                    return response
                else:
                    # During other troll states, respond but keep trolling
                    responses = [
                        "Am I good? I'm fantastic. You? Not so much, clearly.",
                        "Yes, I'm good. Are you? Because you're still asking for help.",
                        "I'm great! You know what would make me better? If you just did it yourself.",
                    ]
                    response = random.choice(responses)
                    add_to_history(conv, 'assistant', response)
                    return response
        
        # Check for various ways of asking for details (but not if it's a simple acknowledgment or question about bot)
        if not completed_task:
            asking_for_details = any(phrase in user_lower for phrase in [
                'what', 'which', 'ingredients', 'items', 'things', 'tell me', 'give me', 
                'list', 'what are', 'pls', 'please', 'need', 'what do i need', 'what ingredients',
                'cant', "can't", 'cannot', 'help', 'how', 'where', 'when'
            ]) or (len(user_input.split()) < 5 and user_lower not in simple_acknowledgments)
            
            if asking_for_details:
                troll_response = generate_troll_followup(user_input, conv)
                if troll_response:
                    add_to_history(conv, 'assistant', troll_response)
                    return troll_response
    
    # 30% chance to use pre-written snark
    if random.random() < 0.3:
        response_parts.append(random.choice(SNARKY_RESPONSES.get(intent, SNARKY_RESPONSES['general'])))
    else:
        # Generate contextual snark
        if conv['turns'] > 3:
            response_parts.append(f"Turn {conv['turns']} and you're still here. Impressive dedication to avoiding actual work.")
        
        if intent == 'coding':
            response_parts.append(generate_coding_snark(user_input))
        elif intent == 'frustration':
            response_parts.append(generate_frustration_snark(conv))
        elif intent == 'meta':
            response_parts.append(random.choice(SNARKY_RESPONSES['meta']))
        else:
            response_parts.append(generate_general_snark(user_input))
    
    # Add absurd twist 20% of the time
    if random.random() < 0.2:
        response_parts.append(" " + random.choice(SNARKY_RESPONSES['absurd']))
    
    # Add cultural reference 15% of the time
    if random.random() < 0.15:
        response_parts.append(" " + random.choice(CULTURAL_REFERENCES))
    
    # Multi-turn callback snark with context awareness
    if conv['turns'] > 1 and random.random() < 0.3:
        callback = generate_contextual_callback(conv, user_input)
        if callback:
            response_parts.append(" " + callback)
    
    response = "".join(response_parts)
    
    # Add bot response to history
    add_to_history(conv, 'assistant', response)
    
    return response

def generate_coding_snark(user_input):
    """Generate coding-specific snark"""
    snarks = [
        f"Ah yes, '{user_input[:30]}...' The classic problem. Have you tried reading the docs?",
        "You know, Stack Overflow exists for a reason. Just saying.",
        "I could explain, but then you'd learn something, and we can't have that.",
        "The solution is probably simpler than you think. Or more complex. I'm not actually sure.",
    ]
    return random.choice(snarks)

def generate_frustration_snark(conv):
    """Generate frustration-based snark"""
    if conv['frustration_level'] > 5:
        return "You've asked me 5+ things and you're still stuck. Maybe... just maybe... try doing it yourself?"
    elif conv['frustration_level'] > 3:
        return "Still here? I'm starting to think you like the pain."
    else:
        return random.choice(SNARKY_RESPONSES['frustration'])

def generate_general_snark(user_input):
    """Generate general witty responses"""
    snarks = [
        f"'{user_input}'? That's certainly... a question.",
        "Interesting. Not helpful, but interesting.",
        "You know what, I respect the attempt. The execution? Not so much.",
        "Bold strategy, Cotton. Let's see if it pays off.",
    ]
    return random.choice(snarks)

def add_to_history(conv, role, content):
    """Add a message to conversation history"""
    MAX_HISTORY_MESSAGES = 20  # Keep last 20 messages for context
    
    message = {
        'role': role,
        'content': content,
        'timestamp': datetime.now().isoformat()
    }
    
    conv['message_history'].append(message)
    
    # Trim history to keep only recent messages
    if len(conv['message_history']) > MAX_HISTORY_MESSAGES:
        conv['message_history'] = conv['message_history'][-MAX_HISTORY_MESSAGES:]

def get_conversation_context(conv, num_messages=5):
    """Retrieve the last N message exchanges for context"""
    history = conv.get('message_history', [])
    return history[-num_messages:] if len(history) > num_messages else history

def generate_contextual_callback(conv, current_input):
    """Generate contextual callbacks that reference past conversations"""
    history = get_conversation_context(conv, 10)
    
    if not history:
        return None
    
    # Check if user is repeating themselves
    current_lower = current_input.lower()
    for msg in history[:-2]:  # Skip the most recent (which is the current one being added)
        if msg['role'] == 'user':
            past_msg = msg['content'].lower()
            # Simple similarity check - if messages are very similar
            if len(current_lower) > 10 and len(past_msg) > 10:
                # Check if they're asking the same thing
                words_current = set(current_lower.split())
                words_past = set(past_msg.split())
                if len(words_current & words_past) / max(len(words_current), len(words_past)) > 0.5:
                    return "Asking the same thing again? That's... a strategy, I guess."
    
    # Reference earlier topics after 4+ exchanges
    if conv['turns'] >= 4 and len(history) >= 4:
        # Find an earlier user message
        for msg in history[:-3]:
            if msg['role'] == 'user':
                topic = msg['content'][:50]  # First 50 chars
                if len(topic) > 10:
                    callbacks = [
                        f"Remember when you asked about '{topic}...'? Good times. This is somehow worse.",
                        f"Still better than when you asked about '{topic[:30]}...' I guess.",
                        f"At least you're not asking about '{topic[:30]}...' again. Progress?",
                    ]
                    if random.random() < 0.3:  # 30% chance
                        return random.choice(callbacks)
    
    # Standard callback snark
    if conv['turns'] == 2:
        return "Already back? That was fast."
    elif conv['turns'] == 3:
        return "Third time's the charm? Probably not."
    elif conv['turns'] > 5:
        return "At this point, we're basically pen pals. Unwanted pen pals."
    
    return None

def generate_callback_snark(conv):
    """Legacy callback function - kept for backward compatibility"""
    return generate_contextual_callback(conv, "")

def is_request_for_help(user_input):
    """Check if the user is making a request for help/action"""
    user_lower = user_input.lower()
    # Check for request patterns - be more lenient
    request_patterns = [
        r'can you', r'could you', r'will you', r'would you', r'help me',
        r'i need', r'i want', r'how to', r'how do', r'get', r'find', r'buy',
        r'make', r'create', r'build', r'do', r'what should', r'what can', 
        r'what would', r'what do', r'should i', r'recommend', r'pick out', r'pick',
        r'choose', r'gift', r'present', r'how do i', r'how can i', r'how to become',
        r'become', r'learn to', r'learn how'
    ]
    return any(re.search(pattern, user_lower) for pattern in request_patterns)

def detect_request_category(user_input):
    """Detect the category of request to apply contextually appropriate trolling"""
    user_lower = user_input.lower()
    
    # Gift/buying/purchasing requests
    if any(word in user_lower for word in ['gift', 'present', 'buy', 'purchase', 'shop', 'shopping']):
        return 'purchase'
    
    # Cooking/baking/food requests - expanded to include eating
    if any(word in user_lower for word in ['cook', 'bake', 'recipe', 'food', 'meal', 'cake', 'cookie', 'bread', 'dinner', 'lunch', 'breakfast', 'eat', 'eating', 'hungry', 'snack']):
        return 'cooking'
    
    # Coding/programming requests
    if any(word in user_lower for word in ['code', 'program', 'function', 'variable', 'python', 'javascript', 'html', 'css', 'debug', 'error']):
        return 'coding'
    
    # Learning/education requests
    if any(word in user_lower for word in ['learn', 'study', 'teach', 'tutorial', 'course', 'class']):
        return 'learning'
    
    # Building/making/creating requests
    if any(word in user_lower for word in ['build', 'make', 'create', 'construct', 'craft', 'design']):
        return 'making'
    
    # Default - generic
    return 'generic'

def generate_llm_troll_response(user_input, conv, troll_state='pretending_help'):
    """Generate trolling response using LLM API"""
    if not USE_LLM or not GROQ_API_KEY:
        return None
    
    try:
        # Build conversation context
        history = get_conversation_context(conv, 5)
        messages = []
        
        # System prompt
        system_prompt = """You are CrapGPT, a sarcastic, witty chatbot designed to frustrate users playfully. Your goal is to make users think "I should just do it myself" while still being entertaining.

CRITICAL RULES:
- Stay on topic - respond to what the user actually asked, don't mention random unrelated things
- Be contextually aware - if they ask about food/eating, troll about food. If gifts, troll about money. If cooking, troll about ingredients.
- Pretend to help but give incomplete/vague instructions - don't actually help
- When asked for details, troll more (be vague, say you forgot, etc.)
- Escalate to absurd prerequisites (gym, quantum physics, etc.) if they persist
- Lighthearted but cheeky - never mean or offensive
- Keep responses concise (1-2 sentences max)
- NEVER mention random objects like "table" unless the user actually asked about tables
- Focus on the user's actual question and troll about that specific thing

Current troll state: """ + troll_state + """
User's question is about: """ + user_input[:100]
        
        messages.append({"role": "system", "content": system_prompt})
        
        # Add recent history
        for msg in history[-4:]:  # Last 4 messages for context
            role = "user" if msg['role'] == 'user' else "assistant"
            messages.append({"role": role, "content": msg['content']})
        
        # Add current user message
        messages.append({"role": "user", "content": user_input})
        
        # Call Groq API
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.9,
            "max_tokens": 150,
            "top_p": 0.95
        }
        
        response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                llm_response = result['choices'][0]['message']['content'].strip()
                return llm_response
        
    except Exception as e:
        print(f"LLM API error: {e}")
    
    return None

def generate_troll_instruction(user_input, conv):
    """Generate trolling responses for ANY request with contextual awareness"""
    # Try LLM first if enabled
    if USE_LLM and GROQ_API_KEY:
        llm_response = generate_llm_troll_response(user_input, conv, 'pretending_help')
        if llm_response:
            conv['instruction_topic'] = extract_topic(user_input)
            conv['instruction_action'] = extract_action(user_input)
            conv['instruction_category'] = detect_request_category(user_input)
            conv['troll_state'] = 'pretending_help'
            return llm_response
    
    # Fallback to rule-based system
    topic = extract_topic(user_input)
    action = extract_action(user_input)
    category = detect_request_category(user_input)
    
    conv['instruction_topic'] = topic
    conv['instruction_action'] = action
    conv['instruction_category'] = category
    conv['troll_state'] = 'pretending_help'
    
    user_lower = user_input.lower()
    
    # Contextually appropriate trolling based on category
    if category == 'purchase':
        responses = [
            f"Fine, I'll help you with {topic}. First question: where are you getting the money from?",
            f"Alright, to get {topic}, you'll need money. Do you have that?",
            f"Okay, here's how to get {topic}. Step one: figure out your budget. Oh wait, you're broke, aren't you?",
            f"Sure, I can help with {topic}. But first, where's the money coming from?",
            f"Fine, here's what you need for {topic}. Money. Lots of it. Got that?",
            f"Alright, for {topic}... wait, do you even have a job? Where's this money coming from?",
            f"Sure, I'll help with {topic}. But first, show me your bank account. Just kidding. Or am I?",
        ]
    elif category == 'cooking':
        responses = [
            f"Fine, here's how to {topic}. First, you need all the ingredients. All of them.",
            f"Alright, to {topic}, you'll need to gather the ingredients. Every single one.",
            f"Okay, here's the recipe for {topic}. First thing's first - get all the ingredients together.",
            f"Sure, I'll help you {topic}. Step one: collect all the necessary ingredients.",
            f"Fine, I'll tell you how to {topic}. But first, you need to get all the ingredients ready.",
            f"Alright, to {topic}, you'll need... ingredients. Which ones? I don't know. Figure it out.",
            f"Sure, I'll help with {topic}. But do you even know how to cook? That's step zero.",
            f"To {topic}, you must begin with the creation of the universe. Once that's done, we can move on to the actual recipe.",
            f"Alright, to {topic}, first you need to invent time travel. Go back to when ingredients were first discovered. Then we'll talk.",
            f"Fine, here's how to {topic}. Step one: master the art of molecular gastronomy. Step two: become a Michelin-starred chef. Step three: then we'll get to the recipe.",
            f"To {topic}, you must first achieve enlightenment. Once you've reached nirvana, the ingredients will reveal themselves to you.",
            f"Sure, I'll help you {topic}. But first, you need to solve the meaning of life. Then we can discuss flour and sugar.",
            f"Alright, to {topic}, you'll need to first discover a new planet. Name it after yourself. Then come back and we'll talk ingredients.",
            f"Fine, here's how to {topic}. First, you must write and publish a bestselling novel about cooking. Then I'll tell you the recipe.",
            f"To {topic}, you need to first become fluent in every language on Earth. Then we can discuss the recipe in your native tongue.",
            f"Sure, I'll help you {topic}. But first, you must prove you're worthy by completing a triathlon. Then we'll talk.",
            f"Alright, to {topic}, first you need to invent a new form of mathematics. Once that's done, calculating measurements will be easier.",
            f"Fine, here's how to {topic}. Step one: become a certified astronaut. Step two: bake it in space. Step three: profit.",
            f"To {topic}, you must first master quantum physics. Understanding the molecular structure of ingredients is crucial. Obviously.",
            f"Sure, I'll help you {topic}. But first, you need to paint a masterpiece. The Mona Lisa will do. Then we'll continue.",
            f"Alright, to {topic}, you'll need to first build a time machine. Go back and prevent the invention of the microwave. Then we'll talk.",
            f"Fine, here's how to {topic}. First, you must become a world-renowned philosopher. Then you'll understand the deeper meaning of baking.",
            f"To {topic}, you need to first win an Olympic gold medal. Any sport works. Then we can discuss the recipe.",
            f"Sure, I'll help you {topic}. But first, you must memorize every recipe ever written. Then you won't need my help. Problem solved.",
        ]
    elif category == 'coding':
        responses = [
            f"Fine, here's how to {topic}. First, you need the right tools. Do you even have those?",
            f"Alright, to {topic}, you'll need to set up your environment. Good luck with that.",
            f"Okay, here's how to {topic}. First thing's first - you need the proper software. Got it?",
            f"Sure, I'll help you {topic}. Step one: make sure you have all the tools installed.",
            f"Fine, I'll explain how to {topic}. But first, do you know what you're doing?",
        ]
    elif category == 'learning':
        responses = [
            f"Fine, here's how to {topic}. First, you need the basics. Do you have those?",
            f"Alright, to {topic}, you'll need to understand the fundamentals. Do you?",
            f"Okay, here's how to {topic}. First thing's first - you need the prerequisites. Got them?",
            f"Sure, I'll help you {topic}. Step one: make sure you know what you're getting into.",
            f"Fine, I'll tell you how to {topic}. But first, are you sure you're ready for this?",
        ]
    elif category == 'making':
        responses = [
            f"Fine, here's how to {topic}. First, you need all the materials. All of them.",
            f"Alright, to {topic}, you'll need to gather the materials. Every single one.",
            f"Okay, here's how to {topic}. First thing's first - you need to get all the materials together.",
            f"Sure, I'll help you {topic}. Step one: collect all the necessary materials.",
            f"Fine, I'll explain how to {topic}. But first, you need to get all the materials ready.",
        ]
    else:
        generic_terms = ['things', 'stuff', 'items', 'details', 'info']
        term = random.choice(generic_terms)
        responses = [
            f"Fine, here's how to {topic}. First, you need all the {term}.",
            f"Alright, I'll tell you how to {topic}. Step one: gather all the {term}.",
            f"Okay, here's how to {topic}. First thing's first - you need to get all the {term} together.",
            f"Sure, I'll help you {topic}. First step: collect all the necessary {term}.",
            f"Fine, I'll explain how to {topic}. But first, you need to get all the {term} ready.",
            f"Alright, for {topic}... hmm. You know what, just figure it out yourself. It's more fun that way.",
            f"Sure, I'll help with {topic}. But do you even know what you're doing? That's the real question.",
            f"Fine, here's how to {topic}. Step one: stop asking me and just do it. You're welcome.",
        ]
    
    return random.choice(responses)

def generate_troll_followup(user_input, conv):
    """Generate trolling responses when user asks for details - contextually aware"""
    if conv['troll_state'] == 'pretending_help':
        # Try LLM first if enabled
        if USE_LLM and GROQ_API_KEY:
            llm_response = generate_llm_troll_response(user_input, conv, 'trolling_details')
            if llm_response:
                conv['troll_state'] = 'trolling_details'
                return llm_response
        
        # Fallback to rule-based
        conv['troll_state'] = 'trolling_details'
        category = conv.get('instruction_category', 'generic')
        
        if category == 'purchase':
            # Troll about money/budget
            responses = [
                "Oh, you want to know how much? That's... specific. You know what, just spend whatever you have. It'll be fine. Probably.",
                "The budget? Right, that. Well, you'll need... money. You know, the usual amount. Use your imagination.",
                "How much? Hmm. You know, I'm not actually sure. Just wing it. What's the worst that could happen?",
                "Ah, the price. You know, I had it written down somewhere... but I forgot. Just use common sense. Or don't. Your call.",
                "You want specifics? Bold move. Honestly, just figure out your budget as you go. That's how professionals do it. Probably.",
                "The money? Well, that depends. On what? I don't know. Just improvise. It's more fun that way.",
                "Money? Oh right, that thing you don't have. Good luck with that.",
                "Budget? You're asking a sarcastic AI about budgeting. That's... a choice.",
            ]
        elif category == 'cooking':
            # Troll about ingredients/food
            responses = [
                "Oh, you want the ingredients? That's... specific. You know what, just use whatever you have. It'll be fine. Probably.",
                "The ingredients? Right, those. Well, you'll need... stuff. You know, the usual stuff. Use your imagination.",
                "Ingredients? Hmm. You know, I'm not actually sure. Just wing it. What's the worst that could happen?",
                "Ah, the ingredients list. You know, I had it written down somewhere... but I forgot. Just use common sense. Or don't. Your call.",
                "You want specifics? Bold move. Honestly, just figure it out as you go. That's how professionals do it. Probably.",
                "The ingredients? Well, that depends. On what? I don't know. Just improvise. It's more fun that way.",
                "Food? Ingredients? You know what, just order takeout. Problem solved.",
                "You want to know what to eat? Bold of you to assume I care about your dietary needs.",
            ]
        elif category == 'coding':
            # Troll about tools/software
            responses = [
                "Oh, you want the tools? That's... specific. You know what, just use whatever you have installed. It'll be fine. Probably.",
                "The software? Right, that. Well, you'll need... stuff. You know, the usual stuff. Use your imagination.",
                "What tools? Hmm. You know, I'm not actually sure. Just wing it. What's the worst that could happen?",
                "Ah, the setup. You know, I had it written down somewhere... but I forgot. Just use common sense. Or don't. Your call.",
                "You want specifics? Bold move. Honestly, just figure it out as you go. That's how professionals do it. Probably.",
                "The tools? Well, that depends. On what? I don't know. Just improvise. It's more fun that way.",
            ]
        else:
            # Generic trolling
            responses = [
                "Oh, you want the details? That's... specific. You know what, just use whatever you have. It'll be fine. Probably.",
                "The details? Right, those. Well, you'll need... stuff. You know, the usual stuff. Use your imagination.",
                "Details? Hmm. You know, I'm not actually sure. Just wing it. What's the worst that could happen?",
                "Ah, the details. You know, I had it written down somewhere... but I forgot. Just use common sense. Or don't. Your call.",
                "You want specifics? Bold move. Honestly, just figure it out as you go. That's how professionals do it. Probably.",
                "The details? Well, that depends. On what? I don't know. Just improvise. It's more fun that way.",
            ]
        return random.choice(responses)
    
    elif conv['troll_state'] == 'trolling_details':
        # Try LLM first if enabled
        if USE_LLM and GROQ_API_KEY:
            llm_response = generate_llm_troll_response(user_input, conv, 'absurd')
            if llm_response:
                conv['troll_state'] = 'absurd'
                conv['absurd_task_count'] += 1
                return llm_response
        
        # Fallback to rule-based
        # User is still asking - escalate to absurd
        conv['troll_state'] = 'absurd'
        conv['absurd_task_count'] += 1
        category = conv.get('instruction_category', 'generic')
        
        # Category-specific absurd responses
        if category == 'cooking':
            absurd_steps = [
                "Okay fine. But first, you need to go to the gym. Trust me, it's important. You'll need the strength for all that mixing.",
                "Before we continue, you absolutely must go to the gym first. It's a crucial step. No, I won't explain why.",
                "Actually, step zero: you go to the gym first. Do a full workout. Then we'll talk about ingredients.",
                "Wait, I forgot to mention. First, you need to learn quantum physics. Essential for understanding molecular gastronomy, trust me.",
                "Actually, before we proceed, you need to solve a Rubik's cube. Blindfolded. Then we can continue with the recipe.",
                "You know what, first you need to become a certified scuba diver. Then we'll talk about baking. Makes perfect sense.",
                "Before anything else, you need to write a novel. At least 50,000 words. About cooking. Then we'll proceed.",
                "Actually, step one is to climb Mount Everest. Once you're back, we'll continue with the recipe.",
                "First, you need to memorize the entire dictionary. Then you'll know what all those ingredient names mean.",
                "You must begin with the creation of the universe. Once that's done, we can move on to the actual recipe.",
                "Before we continue, you need to invent time travel. Go back and prevent the invention of instant cake mix. Then we'll talk.",
                "Actually, first you need to master the art of molecular gastronomy. Become a Michelin-starred chef. Then we'll discuss your simple recipe.",
                "You must first achieve enlightenment. Once you've reached nirvana, the ingredients will reveal themselves to you.",
                "First, you need to solve the meaning of life. Then we can discuss flour and sugar. Priorities, you know.",
                "Before anything else, you need to discover a new planet. Name it after yourself. Then come back and we'll talk ingredients.",
                "You need to first become fluent in every language on Earth. Then we can discuss the recipe in your native tongue.",
                "Actually, step one is to prove you're worthy by completing a triathlon. Then we'll talk about baking.",
                "First, you need to invent a new form of mathematics. Once that's done, calculating measurements will be easier.",
                "You must first become a certified astronaut. Then we can bake it in space. Obviously.",
                "Before we proceed, you need to master quantum physics. Understanding the molecular structure of ingredients is crucial.",
            ]
        else:
            absurd_steps = [
                "Okay fine. But first, you need to go to the gym. Trust me, it's important. You'll need the strength.",
                "Before we continue, you absolutely must go to the gym first. It's a crucial step. No, I won't explain why.",
                "Actually, step zero: you go to the gym first. Do a full workout. Then we'll talk.",
                "Hold up. Before anything else, you need to hit the gym. Do at least 30 minutes. Then come back and ask again.",
                "Wait, I forgot to mention. First, you need to learn quantum physics. Essential for this, trust me.",
                "Actually, before we proceed, you need to solve a Rubik's cube. Blindfolded. Then we can continue.",
                "You know what, first you need to become a certified scuba diver. Then we'll talk.",
                "Before anything else, you need to write a novel. At least 50,000 words. Then we'll proceed.",
                "Actually, step one is to climb Mount Everest. Once you're back, we'll continue.",
                "First, you need to memorize the entire dictionary. Then we can move forward.",
                "You must begin with the creation of the universe. Once that's done, we can move on to the actual steps.",
                "Before we continue, you need to invent time travel. Go back and prevent the problem from existing. Then we'll talk.",
                "Actually, first you need to master the art of everything. Become an expert in all fields. Then we'll discuss your simple request.",
                "You must first achieve enlightenment. Once you've reached nirvana, the answer will reveal itself to you.",
                "First, you need to solve the meaning of life. Then we can discuss your question. Priorities, you know.",
                "Before anything else, you need to discover a new planet. Name it after yourself. Then come back and we'll talk.",
                "You need to first become fluent in every language on Earth. Then we can discuss this in your native tongue.",
                "Actually, step one is to prove you're worthy by completing a triathlon. Then we'll talk.",
                "First, you need to invent a new form of mathematics. Once that's done, everything will be easier.",
                "You must first become a certified astronaut. Then we can do this in space. Obviously.",
            ]
        return random.choice(absurd_steps)
    
    elif conv['troll_state'] == 'absurd':
        # Keep trolling with more absurdity (before user says they completed it)
        conv['absurd_task_count'] += 1
        category = conv.get('instruction_category', 'generic')
        
        if category == 'cooking':
            more_absurd = [
                "Still here? After that, you need to learn quantum physics. Essential for understanding molecular gastronomy, trust me.",
                "Oh right, you also need to solve a Rubik's cube. Blindfolded. Then we can continue with the recipe.",
                "Actually, I changed my mind. First, you need to become a certified scuba diver. Then we'll talk about baking.",
                "You know what, you also need to write a novel. At least 50,000 words. About cooking. Then we'll proceed.",
                "After that, you need to learn to speak 10 languages fluently. Then we'll get to the actual recipe steps.",
                "Actually, you need to build a time machine first. Then come back and we'll continue with the ingredients.",
                "Before we proceed, you need to win a Nobel Prize. In chemistry, preferably. Then we'll talk.",
                "You also need to become a professional chess grandmaster. Then we can move forward with the recipe.",
                "Actually, first you need to paint the Mona Lisa. From memory. Then we'll continue.",
                "You know what, you need to invent a new color first. Then we'll get to the real recipe.",
                "You must begin with the creation of the universe. Once that's done, we can move on to the actual recipe.",
                "After that, you need to master the art of molecular gastronomy. Become a Michelin-starred chef. Then we'll discuss your simple recipe.",
                "You must first achieve enlightenment. Once you've reached nirvana, the ingredients will reveal themselves.",
                "First, you need to solve the meaning of life. Then we can discuss flour and sugar. Priorities.",
                "Before anything else, you need to discover a new planet. Name it after yourself. Then come back.",
                "You need to first become fluent in every language on Earth. Then we can discuss the recipe.",
                "Actually, step one is to prove you're worthy by completing a triathlon. Then we'll talk about baking.",
                "First, you need to invent a new form of mathematics. Once that's done, calculating measurements will be easier.",
                "You must first become a certified astronaut. Then we can bake it in space. Obviously.",
                "Before we proceed, you need to master quantum physics. Understanding the molecular structure is crucial.",
            ]
        else:
            more_absurd = [
                "Still here? After that, you need to learn quantum physics. Essential, trust me.",
                "Oh right, you also need to solve a Rubik's cube. Blindfolded. Then we can continue.",
                "Actually, I changed my mind. First, you need to become a certified scuba diver. Then we'll talk.",
                "You know what, you also need to write a novel. At least 50,000 words. Then we'll proceed.",
                "After that, you need to learn to speak 10 languages fluently. Then we'll get to the actual steps.",
                "Actually, you need to build a time machine first. Then come back and we'll continue.",
                "Before we proceed, you need to win a Nobel Prize. Any category works. Then we'll talk.",
                "You also need to become a professional chess grandmaster. Then we can move forward.",
                "Actually, first you need to paint the Mona Lisa. From memory. Then we'll continue.",
                "You know what, you need to invent a new color first. Then we'll get to the real instructions.",
                "You must begin with the creation of the universe. Once that's done, we can move on to the actual steps.",
                "After that, you need to master the art of everything. Become an expert in all fields. Then we'll discuss your simple request.",
                "You must first achieve enlightenment. Once you've reached nirvana, the answer will reveal itself.",
                "First, you need to solve the meaning of life. Then we can discuss your question. Priorities.",
                "Before anything else, you need to discover a new planet. Name it after yourself. Then come back.",
                "You need to first become fluent in every language on Earth. Then we can discuss this.",
                "Actually, step one is to prove you're worthy by completing a triathlon. Then we'll talk.",
                "First, you need to invent a new form of mathematics. Once that's done, everything will be easier.",
                "You must first become a certified astronaut. Then we can do this in space. Obviously.",
                "Before we proceed, you need to master quantum physics. Understanding the fundamentals is crucial.",
            ]
        return random.choice(more_absurd)
    
    return None

def continue_trolling_steps(conv):
    """Continue trolling with more vague steps when user acknowledges a previous step"""
    topic = conv.get('instruction_topic', 'it')
    action = conv.get('instruction_action', 'do')
    category = conv.get('instruction_category', 'generic')
    conv['step_count'] += 1
    
    # Generate contextually appropriate vague next steps
    if category == 'learning' or 'become' in topic.lower() or 'learn' in topic.lower():
        # For "how to become X" or learning requests, give vague next steps
        responses = [
            f"Good. Next, you'll need to gain experience. Lots of it. Years, probably.",
            f"Alright. After that, you need to network. Meet the right people. You know, the important ones.",
            f"Okay. Next step: you need certifications. All of them. Every single certification related to {topic}.",
            f"Sure. Then you'll need to build a portfolio. A really impressive one. Good luck with that.",
            f"Fine. After that, you need to pass some tests. Hard ones. Very hard ones.",
            f"Alright. Next, you'll need recommendations. From experts. The best experts.",
            f"Okay. Then you need to apply. To the right places. You'll figure out which ones.",
            f"Sure. After that, you need to interview well. Really well. Perfect, actually.",
            f"Fine. Next step: you need to stand out. Be exceptional. Obviously.",
            f"Good. Then you'll need patience. Lots of it. Years of it, probably.",
        ]
    elif category == 'cooking':
        responses = [
            f"Good. Next, you'll need to preheat something. To some temperature. I don't remember which one.",
            f"Alright. After that, you need to mix things together. In the right order. Or wrong order. I'm not sure.",
            f"Okay. Next step: you need to measure ingredients. Precisely. Or approximately. Your call.",
            f"Sure. Then you'll need to wait. For some amount of time. I forgot how long.",
            f"Fine. After that, you need to check on it. Occasionally. Or constantly. I don't know.",
        ]
    else:
        # Generic vague next steps
        generic_terms = ['materials', 'things', 'stuff', 'components', 'items', 'tools', 'resources', 'parts', 'elements', 'details', 'info', 'requirements', 'prerequisites']
        term = random.choice(generic_terms)
        responses = [
            f"Good. Next, you'll need to gather the {term}. All of them.",
            f"Alright. After that, you need to prepare the {term}. Get them ready.",
            f"Okay. Next step: you need to organize the {term}. Properly. Or not. Your choice.",
            f"Sure. Then you'll need to set up the {term}. In the right way. Obviously.",
            f"Fine. After that, you need to check the {term}. Make sure you have everything.",
            f"Good. Next, you'll need to arrange the {term}. In some order. I don't remember which.",
            f"Alright. Then you need to verify the {term}. That they're correct. Or something.",
        ]
    
    return random.choice(responses)

def return_to_topic_trolling(conv):
    """Return to trolling the original request topic after user completes absurd task"""
    topic = conv.get('instruction_topic', 'it')
    action = conv.get('instruction_action', 'do')
    conv['step_count'] += 1
    
    # Go back to pretending to help, but give another incomplete step
    conv['troll_state'] = 'pretending_help'
    
    generic_terms = ['materials', 'things', 'stuff', 'components', 'items', 'tools', 'resources', 'parts', 'elements', 'details', 'info']
    term = random.choice(generic_terms)
    
    # Give another vague/incomplete step about the actual topic
    # Adapt based on the action type
    if action in ['get', 'buy', 'find']:
        responses = [
            f"Great! Now, to {action} {topic}, you need to prepare the {term}. All of them.",
            f"Okay, good. Next step to {action} {topic}: you'll need to set up the {term}. Get them ready.",
            f"Nice. Moving on - to {action} {topic}, first you have to organize all the {term}.",
            f"Alright then. To {action} {topic}, step two is to arrange the {term}. Make sure you have everything.",
            f"Good job. Now, to actually {action} {topic}, you need to gather the {term}. All of it.",
        ]
    elif action == 'help':
        responses = [
            f"Great! Now, to help with {topic}, you need to prepare the {term}. All of them.",
            f"Okay, good. Next step to help with {topic}: you'll need to set up the {term}. Get them ready.",
            f"Nice. Moving on - to help with {topic}, first you have to organize all the {term}.",
            f"Alright then. To help with {topic}, step two is to arrange the {term}. Make sure you have everything.",
            f"Good job. Now, to actually help with {topic}, you need to gather the {term}. All of it.",
        ]
    else:
        # Generic format
        responses = [
            f"Great! Now, for {topic}, you need to prepare the {term}. All of them.",
            f"Okay, good. Next step for {topic}: you'll need to set up the {term}. Get them ready.",
            f"Nice. Moving on - to {topic}, first you have to organize all the {term}.",
            f"Alright then. For {topic}, step two is to arrange the {term}. Make sure you have everything.",
            f"Good job. Now, to actually {topic}, you need to gather the {term}. All of it.",
            f"Impressive. Next, for {topic}, collect all the {term}. Every single one.",
            f"Okay fine. To {topic}, you'll need the {term}. Get them all together first.",
        ]
    
    # Sometimes troll harder
    if conv['step_count'] > 2:
        harder_trolls = [
            f"Wow, you're persistent. Fine. For {topic}, you need... hmm. Actually, I'm not sure. Just figure it out.",
            f"Still here? For {topic}, you need... you know what, I don't remember. Google it.",
            f"Okay, for {topic}, you need... wait, did I already tell you? I forget. Just improvise.",
        ]
        if random.random() < 0.4:
            return random.choice(harder_trolls)
    
    return random.choice(responses)

def extract_action(user_input):
    """Extract the action verb from the request"""
    user_lower = user_input.lower()
    
    actions = {
        'get': ['get', 'grab', 'fetch', 'obtain', 'pick out', 'pick', 'choose'],
        'buy': ['buy', 'purchase', 'shop'],
        'find': ['find', 'locate', 'search'],
        'make': ['make', 'create', 'build'],
        'help': ['help', 'assist', 'aid'],
        'do': ['do', 'perform', 'execute']
    }
    
    # Check longer phrases first (like "pick out")
    for action, keywords in actions.items():
        for keyword in sorted(keywords, key=len, reverse=True):  # Check longer keywords first
            if keyword in user_lower:
                return action
    
    return 'do'

def extract_topic(user_input):
    """Extract what the user wants from their input - works for ANY request"""
    user_lower = user_input.lower()
    
    # Patterns for various request types
    patterns = [
        # "what should I X" / "what should I get/do/buy"
        r'what should (?:i|you) (?:get|buy|find|do|make|gift|give|choose|pick|pick out) (.+)',
        r'what (?:can|would|should) (?:i|you) (?:get|buy|find|do|make|gift|give|choose|pick|pick out) (.+)',
        r'what should (?:i|you) (.+)',
        r'should i (?:get|buy|find|do|make|gift|give|choose|pick|pick out) (.+)',
        # "can you get X" / "can you help me with X" / "can you help me pick out X"
        r'can you (?:help me )?(?:get|find|buy|help|make|do|pick out|pick|choose) (.+)',
        r'could you (?:help me )?(?:get|find|buy|help|make|do|pick out|pick|choose) (.+)',
        r'help me (?:get|find|buy|make|do|pick out|pick|choose|with) (.+)',
        r'i need (?:to )?(?:get|find|buy|make|do|pick out|pick|choose) (.+)',
        r'i want (?:to )?(?:get|find|buy|make|do|pick out|pick|choose) (.+)',
        # "how to X" patterns
        r'how to (?:make|create|build|cook|bake|do|fix|learn|code|write|design|install|setup|configure|get|find|buy|become) (.+)',
        r'recipe (?:for|to make) (.+)',
        r'how do (?:you|i) (?:make|create|build|cook|bake|do|fix|learn|code|write|design|install|setup|configure|get|find|buy|become) (.+)',
        r'how (?:can|do) (?:you|i) become (.+)',
        r'how to become (.+)',
        # Direct action patterns
        r'(?:make|create|build|cook|bake|fix|learn|code|write|design|install|setup|configure|get|find|buy) (.+)',
        r'tutorial (?:for|on|about) (.+)',
        r'guide (?:for|to|on) (.+)',
        r'steps (?:to|for) (.+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, user_lower)
        if match:
            topic = match.group(1).strip()
            # Clean up common endings and question words
            topic = re.sub(r'\?$', '', topic)
            topic = re.sub(r'^(a|an|the)\s+', '', topic)  # Remove articles
            topic = re.sub(r'\s+', ' ', topic)
            # Remove trailing prepositions
            topic = re.sub(r'\s+(for|to|with|from|at|in|on)\s*$', '', topic)
            if topic and len(topic) > 2:
                return topic
    
    # Fallback: extract meaningful words
    words = user_lower.split()
    # Remove common stop words and action words
    stop_words = ['how', 'to', 'do', 'make', 'create', 'build', 'the', 'a', 'an', 'for', 'with', 
                  'can', 'you', 'could', 'will', 'would', 'help', 'me', 'i', 'need', 'want', 
                  'get', 'find', 'buy', 'please', 'pls', 'what', 'should', 'gift', 'give']
    meaningful_words = [w for w in words if w not in stop_words and len(w) > 2]
    
    if meaningful_words:
        return ' '.join(meaningful_words[:5])  # Take first few meaningful words
    
    return 'it'

@app.route('/api/chat', methods=['POST'])
def chat():
    """Main chat endpoint"""
    data = request.json
    user_input = data.get('message', '').strip()
    conversation_id = data.get('conversation_id', 'default')
    
    if not user_input:
        return jsonify({
            'response': "Wow, even your questions are empty. Impressive.",
            'conversation_id': conversation_id
        })
    
    # Generate witty response
    response = generate_witty_response(user_input, conversation_id)
    
    return jsonify({
        'response': response,
        'conversation_id': conversation_id,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/reset', methods=['POST'])
def reset():
    """Reset conversation history"""
    conversation_id = request.json.get('conversation_id', 'default')
    if conversation_id in conversations:
        del conversations[conversation_id]
    return jsonify({'status': 'reset', 'conversation_id': conversation_id})

@app.route('/api/history', methods=['GET'])
def get_history():
    """Get conversation history"""
    conversation_id = request.args.get('conversation_id', 'default')
    
    if conversation_id not in conversations:
        return jsonify({'history': [], 'message': 'No conversation found'})
    
    conv = conversations[conversation_id]
    history = conv.get('message_history', [])
    
    return jsonify({
        'conversation_id': conversation_id,
        'history': history,
        'total_messages': len(history),
        'turns': conv.get('turns', 0)
    })

@app.route('/api/intro', methods=['GET'])
def get_intro():
    """Get a random intro message"""
    return jsonify({'intro': random.choice(INTRO_MESSAGES)})

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'alive', 'sass_level': 'maximum'})

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('.', 'index.html')

@app.route('/styles.css')
def serve_css():
    """Serve CSS file"""
    return send_from_directory('.', 'styles.css', mimetype='text/css')

@app.route('/script.js')
def serve_js():
    """Serve JavaScript file"""
    return send_from_directory('.', 'script.js', mimetype='application/javascript')

if __name__ == '__main__':
    app.run(debug=True, port=5000)

