import base64
import time
import os
import json
import re
from bs4 import BeautifulSoup as bs4
from requests import Session
from random import choice
from pyfzf.pyfzf import FzfPrompt


BASE_URL = 'http://hdrezka.tv' #format: http://hdrezka.tv

user_agent_list = [

    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.246'
    'Mozilla/5.0 (X11; CrOS x86_64 8172.45.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.64 Safari/537.36'
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_2) AppleWebKit/601.3.9 (KHTML, like Gecko) Version/9.0.2 Safari/601.3.9'
    'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.111 Safari/537.36'
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:94.0) Gecko/20100101 Firefox/94.0'
]

ses = Session()
ses.headers = {'User-Agent': choice(user_agent_list)}


fzf = FzfPrompt()

def watchMovie(url,subtitle):
    if subtitle == "":
        os.system(f'mpv -fs {url}')
    else:
        os.system(f'mpv -fs {url} --sub-file={subtitle}')


def chooseQuality(urls,subtitle):
    allQuality = re.findall(r'\[(\w*)\]', urls)
    choose = allQuality.index(fzf.prompt(allQuality)[0])
    url = re.findall(r'\[\w*\](\S*):hls', urls)[choose]
    watchMovie(url, subtitle)


def getSubtitles(subtitles):
    languages = re.findall(r"\[(\w*)\]",subtitles)
    choose = languages.index(fzf.prompt(languages)[0])
    subtitleUrls = re.findall(r"\[\w*\](\S*)", subtitles.replace(',', ' '))
    return subtitleUrls[choose]


def getEpisodeUrlsB64(season, episode, translatorId, filmId):
    payload = {
            'id' : filmId,
            'translator_id' : translatorId,
            'season': str(season + 1),
            'episode' : str(episode + 1),
            'action' : 'get_stream'
            }
    response = ses.post(f'{BASE_URL}/ajax/get_cdn_series/?t=' + str(int(time.time()*1000)), data=payload)
    subtitle = ""
    data = json.loads(response.text)
    if data['subtitle']:
        subtitle = getSubtitles(data['subtitle'])
    if not data['url']:
        raise Exception('Сервер не вернул ссылку! Скорее всего контент не доступен в вашем регионе.')
    b64 = data['url'][2:]
    while '//_//' in b64:
        b64 = b64[:b64.find('//_//')] + b64[b64.find('/_//')+20:]
    return b64, subtitle


def getEpisodeUrls(season, episode, translatorId, filmId):
    b64, subtitle = getEpisodeUrlsB64(season, episode, translatorId, filmId)
    flag = True
    while flag:
        try:
            b64 = str(base64.b64decode(b64).decode())
            flag = False
        except Exception as e:
            b64 = getEpisodeUrlsB64(season, episode, translatorId, filmId)
    chooseQuality(b64, subtitle)


def getMovieUrlsB64(translatorId, filmId):
    payload = {'id' : filmId, 'translator_id' : translatorId, 'action' : 'get_movie'}
    response = ses.post(f'{BASE_URL}/ajax/get_cdn_series/?t=' + str(time.time()), data=payload)
    data = json.loads(response.content)
    subtitleUrl = ""
    if data['subtitle']:
        subtitleUrl = getSubtitles(data['subtitle'])
    if not data['url']:
        raise Exception('Сервер не вернул ссылку! Скорее всего контент не доступен в вашем регионе.')
    b64 = data['url'][2:]
    while '//_//' in b64:
        b64 = b64[:b64.find('//_//')] + b64[b64.find('/_//')+20:]

    return b64, subtitleUrl


def getEpisodes(filmId, translatorId):
    payload = {
            'id' : filmId,
            'translator_id' : translatorId,
            'action' : 'get_episodes'
            }
    response = ses.post(f'{BASE_URL}/ajax/get_cdn_series/?t=' + str(time.time()), data=payload)
    data = json.loads(response.content)
    if data['success'] == False:
        b64, subtitleUrl = getMovieUrlsB64(translatorId, filmId)
        flag = True
        while flag:
            try:
                b64 = str(base64.b64decode(b64).decode())
                flag = False
            except Exception as e:
                b64 = getEpisodeUrlsB64(season, episode, translatorId, filmId)
        
        chooseQuality(b64, subtitleUrl)
    else:
        parse = bs4(data['seasons'], 'lxml')
        allSeasons = parse.findAll('li')
        seasons = []
        for season in allSeasons:
            seasons.append(season.text)
        season = seasons.index(fzf.prompt(seasons)[0])
        parse = bs4(data['episodes'], 'lxml')
        allEpisodes = parse.findAll('li', {'data-season_id' : str(season+1)})
        episodes = []
        for episode in allEpisodes:
            episodes.append(episode.text)
        episode = episodes.index(fzf.prompt(episodes)[0])
        getEpisodeUrls(season, episode, translatorId, filmId)


def chooseTranslators(url):
    filmId = re.findall(r'/(\w*)-', url)[0]
    response = ses.get(url)
    html = bs4(response.content, 'lxml')
    allTranslators = html.findAll('li', class_='b-translator__item')
    if allTranslators != []:
        allId = []
        names = []
        for translator in allTranslators:
            allId.append(translator['data-translator_id'])
            name = translator.text
            try:
                name += ' (' + translator.find('img')['title'] + ')'
            except:
                pass
            names.append(name)
        choose = fzf.prompt(names)[0]
        getEpisodes(filmId, allId[names.index(choose)])
    else:
        try:
            translatorId = re.findall(r'SeriesEvents\(\d*,(\d*)', response.text)[0]
        except:
            translatorId = re.findall(r'MoviesEvents\(\d*, (\d*)', response.text)[0]
        getEpisodes(filmId, translatorId)


def choose(allFilms):
    urls = []
    names = []
    for film in allFilms:
        name = film.find('div', class_='b-content__inline_item-link').text
        url = film.find('a', href=True)['href']
        type = film.find('i', class_='entity').text
        urls.append(url)
        names.append(name)
    choose = fzf.prompt(names)[0]
    chooseTranslators(urls[names.index(choose)])

def search(query):
    response = ses.get(f'{BASE_URL}/search/?do=search&subaction=search&q=' + query)
    html = bs4(response.content, 'lxml')
    allFilms = html.findAll('div', class_='b-content__inline_item')
    choose(allFilms)

if __name__ == '__main__':
    query = input('Введите название фильма/сериала, который будете смотреть: ').replace(' ', '+')
    search(query)
