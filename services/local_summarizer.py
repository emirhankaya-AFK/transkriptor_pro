import math
import re
from collections import Counter

# Turkish stopwords list
TURKISH_STOPWORDS = {
    "ve", "veya", "ama", "fakat", "lakin", "ancak", "ile", "de", "da", "ki", "bir", "bu", "şu", "o", 
    "için", "gibi", "kadar", "en", "daha", "her", "hepsi", "hiç", "ise", "çünkü", "nasıl", "neden", 
    "niçin", "kim", "neyse", "belki", "bazen", "bazı", "tüm", "bütün", "kez", "defa", "kere", "yani", 
    "şey", "şeyler", "ben", "sen", "biz", "siz", "onlar", "bana", "sana", "ona", "bize", "size", 
    "onlara", "beni", "seni", "onu", "bizi", "sizi", "onları", "benim", "senin", "onun", "bizim", 
    "sizin", "onun", "onların", "birkaç", "biri", "birçok", "göre", "karşı", "sonra", "önce", "beri", 
    "dek", "ilgili", "olarak", "olan", "olanlar", "kendi", "kendisi", "altı", "yedi", "sekiz", "dokuz", 
    "on", "var", "yok", "mi", "mı", "mu", "mü", "ise", "hiçbir", "herkes", "kimse", "hiçbiri",
    "eee", "ııı", "şimdi", "biliyorsunuz", "bakın", "aslında", "yani", "şöyle",
    "maalesef", "tabii", "tamam", "arkadaşlar", "diyebiliriz"
}

def clean_word(word):
    """Clean a word by removing punctuation and converting to lowercase."""
    word = word.lower()
    # Replace Turkish chars mapping for lowercasing dotless i correctly
    word = word.replace('I', 'ı').replace('İ', 'i')
    word = re.sub(r'[^\w\s]', '', word)
    return word

def segment_transcript(transcript_snippets):
    """
    Groups transcript snippets into sentences.
    If punctuation density is low, segments text into ~30-word sentences.
    """
    raw_text = " ".join([item.get('text', '') for item in transcript_snippets])
    
    # Calculate punctuation density
    punctuation_count = len(re.findall(r'[.!?]', raw_text))
    words = raw_text.split()
    word_count = len(words)
    
    sentences = []
    
    if word_count == 0:
        return sentences
        
    punctuation_density = punctuation_count / word_count if word_count > 0 else 0
    
    # Threshold for low punctuation (e.g. less than 1 punctuation mark per 40 words)
    if punctuation_density < 0.025:
        # Segment into chunks of ~30 words
        chunk_size = 30
        for i in range(0, word_count, chunk_size):
            chunk_words = words[i:i+chunk_size]
            chunk_text = " ".join(chunk_words)
            
            # Estimate start time from snippets
            # Find the snippet closest to this word index
            start_time = 0.0
            word_idx = 0
            for snippet in transcript_snippets:
                s_words = snippet.get('text', '').split()
                if word_idx <= i < word_idx + len(s_words):
                    start_time = snippet.get('start', 0.0)
                    break
                word_idx += len(s_words)
                
            sentences.append({
                'text': chunk_text,
                'start': start_time,
                'index': len(sentences)
            })
    else:
        # Segment by punctuation boundaries, keeping track of start times
        current_sentence = []
        current_start = None
        
        for snippet in transcript_snippets:
            text = snippet.get('text', '')
            if current_start is None:
                current_start = snippet.get('start', 0.0)
                
            # If snippet contains sentence endings
            parts = re.split(r'(?<=[.!?])\s+', text)
            if len(parts) > 1:
                # First part finishes the current sentence
                current_sentence.append(parts[0])
                sentences.append({
                    'text': " ".join(current_sentence),
                    'start': current_start,
                    'index': len(sentences)
                })
                # Middle parts are complete sentences
                for part in parts[1:-1]:
                    sentences.append({
                        'text': part,
                        'start': snippet.get('start', 0.0),
                        'index': len(sentences)
                    })
                # Last part starts a new sentence
                current_sentence = [parts[-1]]
                current_start = snippet.get('start', 0.0)
            else:
                current_sentence.append(text)
                
        if current_sentence:
            sentences.append({
                'text': " ".join(current_sentence),
                'start': current_start,
                'index': len(sentences)
            })
            
    return sentences

def _generate_extractive_summary(transcript_snippets, max_sentences=5, max_chars=900, bullets=False):
    """
    Generates a 4-6 sentence Turkish summary of the transcript
    using sentence scoring based on word frequencies.
    """
    sentences = segment_transcript(transcript_snippets)
    if not sentences:
        return "Özet çıkarılabilecek uygun bir metin bulunamadı."
        
    # Clean and tokenize all words for frequency analysis
    all_words = []
    for s in sentences:
        words = s['text'].split()
        for w in words:
            cleaned = clean_word(w)
            if cleaned and cleaned not in TURKISH_STOPWORDS:
                all_words.append(cleaned)
                
    if not all_words:
        # Fallback if everything was stopwords
        all_words = [clean_word(w) for s in sentences for w in s['text'].split() if clean_word(w)]
        
    word_frequencies = Counter(all_words)
    
    # Score sentences by distinctive content words. This prevents repeated
    # spoken filler from making the opening sentences dominate the summary.
    scored_sentences = []
    for s in sentences:
        words = [clean_word(w) for w in s['text'].split()]
        content_words = [w for w in words if w and w not in TURKISH_STOPWORDS]
        unique_words = set(content_words)
        score = sum(math.log1p(word_frequencies[w]) for w in unique_words)
        normalized_score = score / math.sqrt(max(1, len(content_words)))

        if len(content_words) < 4:
            normalized_score *= 0.35

        scored_sentences.append({
            'score': normalized_score,
            'sentence': s,
            'words': unique_words,
        })

    top_n = min(max_sentences, len(scored_sentences))
    top_n = max(min(4, len(scored_sentences)), top_n)

    # Maximal marginal relevance: keep different points instead of five
    # nearly identical sentences from one part of the transcript.
    remaining = scored_sentences[:]
    selected = []
    selected_words = set()
    while remaining and len(selected) < top_n:
        best = None
        best_value = float('-inf')
        for candidate in remaining:
            overlap = 0
            if candidate['words']:
                overlap = len(candidate['words'] & selected_words) / len(candidate['words'])
            value = candidate['score'] * (1 - 0.65 * overlap)
            if value > best_value:
                best = candidate
                best_value = value
        selected.append(best['sentence'])
        selected_words.update(best['words'])
        remaining.remove(best)

    top_sentences = selected
    
    # Sort top sentences chronologically (by original index)
    top_sentences.sort(key=lambda x: x['index'])
    
    # Build final summary paragraph
    summary_parts = []
    used_chars = 0
    for s in top_sentences:
        text = s['text'].strip()
        if not text:
            continue
            
        # Ensure it starts with uppercase
        if len(text) > 0:
            text = text[0].upper() + text[1:]
            
        # Ensure it ends with punctuation
        if not text.endswith(('.', '!', '?')):
            text += '.'

        remaining = max_chars - used_chars
        if remaining <= 20:
            break
        if len(text) > remaining:
            text = text[:remaining].rsplit(" ", 1)[0].rstrip(" ,;:") + "."
        if text:
            summary_parts.append(text)
            used_chars += len(text) + 1

        if used_chars >= max_chars:
            break
        
    if bullets:
        summary = "\n".join(f"- {part}" for part in summary_parts)
    else:
        summary = " ".join(summary_parts)
    return summary


def generate_local_summary(transcript_snippets, max_sentences=5, max_chars=900, bullets=False):
    """Prefer coherent local rewriting, with the deterministic method as fallback."""
    try:
        from transkriptor_pro.config import Config
        if Config.ABSTRACTIVE_SUMMARY_ENABLED:
            from transkriptor_pro.services.llama_summarizer import (
                generate_llama_summary,
            )
            generated = generate_llama_summary(
                transcript_snippets,
                max_chars=max_chars,
                detailed=bullets,
            )
            if generated:
                return generated
    except Exception:
        # A missing model, an offline first download, or an OOM must not break
        # transcription; the deterministic summarizer remains available.
        import logging
        logging.getLogger(__name__).exception("Abstractive summary failed; using extractive fallback")

    return _generate_extractive_summary(
        transcript_snippets,
        max_sentences=max_sentences,
        max_chars=max_chars,
        bullets=bullets,
    )
