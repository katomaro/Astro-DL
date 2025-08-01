import json
import requests
import re
from typing import Dict, List, Optional, Any

from urllib.parse import urlparse, urljoin, parse_qs, urlunparse

from bs4 import BeautifulSoup
import pathlib
import m3u8
import re
import base64
from yt_dlp import YoutubeDL


def request_platform_url() -> str:
    """
    Request the platform URL from the user.
    
    Returns:
        str: The validated platform URL
    """
    print("=== Configuração da Plataforma ===")
    print("Por favor, forneça a URL de login da plataforma astronmembers.")
    print("Exemplo: https://escolaateaaprovac.astronmembers.com/entrar&logout")
    
    while True:
        url = input("\nURL da plataforma: ").strip()
        
        if not url:
            print("Erro: A URL não pode estar vazia. Tente novamente.")
            continue
        if not url.startswith(('http://', 'https://')):
            print("Erro: A URL deve começar com 'http://' ou 'https://'. Tente novamente.")
            continue
        # In some cases, the course author can set a different domain through their DNS
        if 'astronmembers.com' not in url:
            print("Aviso: A URL não parece ser do domínio astronmembers.com")
            confirmation = input("Deseja continuar mesmo assim? (s/n): ").strip().lower()
            if confirmation not in ['s', 'sim', 'y', 'yes']:
                continue
        return url

def request_credentials() -> Dict[str, str]:
    """
    Request login credentials from the user.
    
    Returns:
        Dict[str, str]: Dictionary containing email and password
    """
    print("\n=== Credenciais de Login ===")
    print("Por favor, forneça suas credenciais para acessar a plataforma.")
    


    while True:
        email = input("\nEmail: ").strip()
        
        if not email:
            print("❌ Erro: O email não pode estar vazio. Tente novamente.")
            continue
            
        # Basic email validation
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            print("❌ Erro: Formato de email inválido. Tente novamente.")
            continue
            
        break
    
    while True:
        password = input("Senha: ").strip()
        
        if not password:
            print("Erro: A senha não pode estar vazia. Tente novamente.")
            continue
            
        if len(password) < 6:
            print("Aviso: A senha parece muito curta.")
            confirmation = input("Deseja continuar mesmo assim? (s/n): ").strip().lower()
            if confirmation not in ['s', 'sim', 'y', 'yes']:
                continue
        
        break
    return {
        'email': email,
        'password': password
    }

def validate_configuration(platform_url: str, credentials: Dict[str, str]) -> bool:
    """
    Validate the configuration provided by the user.
    
    Args:
        platform_url (str): The platform URL to validate
        credentials (Dict[str, str]): Dictionary containing email and password
        
    Returns:
        bool: True if configuration is valid, False otherwise
    """
    print("\n=== Validação da Configuração ===")
    print(f"URL da plataforma: {platform_url}")
    print(f"Email: {credentials['email']}")
    print(f"Senha: {'*' * len(credentials['password'])}")
    
    # confirmation = input("\nAs informações estão corretas? (s/n): ").strip().lower()
    return True # confirmation in ['s', 'sim', 'y', 'yes']

def create_authenticated_session(platform_url: str, credentials: Dict[str, str]) -> requests.Session:
    """
    Create a session to the platform.
    
    Args:
        platform_url (str): The platform URL
        credentials (Dict[str, str]): Dictionary containing email and password
        
    Returns:
        requests.Session: A session object for the platform
    """
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Origin': platform_url.rsplit('/', 1)[0],
        'Referer': platform_url
    })

    # Get the login URL from the platform URL
    session.get(platform_url)

    parsed_url = urlparse(platform_url)
    login_url = f"{parsed_url.scheme}://{parsed_url.netloc}/entrar"
    
    print(f"\nTentando fazer login em {login_url}...")

    login_data = {
        'return': (None, ''),
        'login': (None, credentials['email']),
        'senha': (None, credentials['password']),
    }

    try:
        response = session.post(login_url, files=login_data)
        response.raise_for_status()

    except requests.exceptions.RequestException as e:
        print(f"❌ An error occurred during login: {e}")
        return None
    
    return session

def _parse_courses_from_html(html_content: str, base_url: str) -> List[Dict[str, str]]:
    """
    (Helper Function) Parses the dashboard HTML to extract a list of all unique courses,
    ignoring the "Continuar Progresso" section.

    Args:
        html_content: The HTML content of the dashboard page as a string.
        base_url: The base URL of the platform to resolve relative links.

    Returns:
        A list of dictionaries, each containing the 'title' and 'url' of a course.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    all_courses = []
    processed_urls = set()

    for carousel in soup.find_all('div', class_='box-slider-cursos'):
        for link_tag in carousel.select('div.swiper-slide a[href]'):
            relative_url = link_tag['href']
            
            if not relative_url.startswith('curso/'):
                continue
            
            full_url = urljoin(base_url, relative_url)
            if full_url not in processed_urls:
                try:
                    slug = relative_url.split('/')[1]
                    title = slug.replace('-', ' ').title()
                    all_courses.append({'title': title, 'url': full_url})
                    processed_urls.add(full_url)
                except IndexError:
                    continue
    
    return all_courses

def get_course_list(session: requests.Session, platform_url: str) -> List[Dict[str, str]]:
    """
    Fetches the dashboard page and returns a list of all courses available to the user.

    Args:
        session: An authenticated requests.Session object.
        platform_url: The base URL of the platform.

    Returns:
        A list of courses or None if an error occurs.
    """
    print("\n🔎 Buscando a lista de cursos no dashboard...")
    
    # The dashboard is usually at the '/dashboard' endpoint
    dashboard_url = urljoin(platform_url, 'dashboard')
    
    try:
        response = session.get(dashboard_url)
        response.raise_for_status()

        # Use the base URL from the final response URL after any redirects
        final_base_url = f"{urlparse(response.url).scheme}://{urlparse(response.url).netloc}"
        
        courses = _parse_courses_from_html(response.text, final_base_url)
        if not courses:
            print("⚠️ Nenhum curso encontrado no dashboard.")
            return []
            
        print(f"✅ Sucesso! {len(courses)} cursos encontrados.")
        return courses

    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao buscar a página de cursos: {e}")
        return None

def _parse_course_structure_from_html(html_content: str, base_url: str) -> dict:
    """
    (Helper Function) Parses the course page HTML to extract its full structure,
    including modules and lessons.

    Args:
        html_content: The HTML content of the course page.
        base_url: The base URL to resolve relative links.

    Returns:
        A dictionary representing the course structure.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    course_container = soup.select_one('div.modulos.videos')
    if not course_container:
        return {}

    course_title_tag = course_container.find('div', class_='modulo-head-content').find('h2')
    course_title = course_title_tag.text.strip() if course_title_tag else "Unknown Course"

    course_data = {"course_title": course_title, "modules": []}

    for module_dl in course_container.find_all('dl'):
        module_title_tag = module_dl.find('dt').find('h3')
        if not module_title_tag:
            continue
        
        module_title = module_title_tag.text.strip()
        lessons_data = []

        for lesson_item in module_dl.select('dd li.aulabox'):
            link_tag = lesson_item.find_parent('a')
            title_tag = lesson_item.find('h6')
            
            if not (link_tag and title_tag):
                continue

            lessons_data.append({
                "id": lesson_item.get('data-aulaid'),
                "title": title_tag.text.strip(),
                "url": urljoin(base_url, link_tag['href']),
                "is_completed": 'concluida' in lesson_item.get('class', [])
            })
        
        course_data["modules"].append({
            "module_title": module_title,
            "lessons": lessons_data
        })

    return course_data

def get_course_details(session: requests.Session, course_url: str) -> dict:
    """
    Fetches the course page by manually handling redirects and returns its 
    full structure as a dictionary.

    Args:
        session: An authenticated requests.Session object.
        course_url: The URL of the course to fetch.

    Returns:
        A dictionary with the course structure or None if an error occurs.
    """
    print(f"\n🔎 Buscando detalhes para o curso em: {course_url}")
    
    try:
        initial_response = session.get(course_url, allow_redirects=False)
        initial_response.raise_for_status()

        final_response = None

        if initial_response.is_redirect:
            redirect_url = initial_response.headers['location']
            print(f"Redirect detectado. Acessando: {redirect_url}")
            
            final_response = session.get(redirect_url)
            final_response.raise_for_status()
        else:
            final_response = initial_response

        base_url = f"{urlparse(final_response.url).scheme}://{urlparse(final_response.url).netloc}"
        structure = _parse_course_structure_from_html(final_response.text, base_url)
        
        if not structure.get("modules"):
            print("⚠️ A estrutura do curso não pôde ser encontrada na página.")
            return None
            
        print("✅ Detalhes do curso extraídos com sucesso!")
        return structure

    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao buscar a página do curso: {e}")
        return None

def get_lesson_content(session: requests.Session, lesson_url: str) -> Optional[Dict[str, Any]]:
    """
    Fetches a lesson page and extracts the video player URL, description, and attachments.

    This function navigates to a specific lesson's URL, parses the HTML to find the
    embedded video player, the content in the description tab, and any file attachments.

    Args:
        session: An authenticated requests.Session object to perform the GET request.
        lesson_url: The full URL of the lesson page to scrape.

    Returns:
        A dictionary containing 'player_url', 'description', and 'attachments'.
        'attachments' is a list of dictionaries, each with 'name' and 'url'.
        Returns None if the request fails or if critical content cannot be parsed.
    """
    try:
        response = session.get(lesson_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        player_iframe = soup.select_one('iframe.streaming-video-url')
        player_url = player_iframe['src'] if player_iframe else None

        description_container = soup.select_one('div.aba-descricao')
        description = None
        if description_container:
            not_found_div = description_container.select_one('div.content-notfound')
            if not not_found_div:
                description = description_container.get_text(separator='\n', strip=True)

        attachments = []
        attachments_container = soup.select_one('div.aba-anexos')
        if attachments_container:
            attachment_links = attachments_container.select('div.lista-anexos a')
            for link in attachment_links:
                name_tag = link.select_one('p')
                name = name_tag.get_text(strip=True) if name_tag else "Anexo sem nome"
                
                relative_url = link.get('href')
                if not relative_url:
                    continue
                
                absolute_url = urljoin(lesson_url, relative_url)
                
                attachments.append({
                    'name': name,
                    'url': absolute_url,
                })

        return {
            'player_url': player_url,
            'description': description,
            'attachments': attachments
        }

    except requests.exceptions.RequestException as e:
        print(f"❌ Nao foi possivel obter o conteudo da aula. Erro: {e}")
        return None

def convert_panda_video_url(url: str) -> str:
    """Converts a Panda Video embed URL to its M3U8 playlist format."""
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    video_id = query_params.get('v', [None])[0]
    if not video_id:
        raise ValueError("URL is missing the required 'v' query parameter.")
    new_netloc = parsed_url.netloc.replace('player', 'b', 1)
    new_path = f"/{video_id}/playlist.m3u8"
    new_url_components = (
        parsed_url.scheme, new_netloc, new_path, '', '', ''
    )
    return urlunparse(new_url_components)

def get_highest_quality_stream(embed_url: str, custom_referer: str):
    """
    Fetches the M3U8 playlist and returns the highest quality stream.

    Args:
        embed_url: The original embed URL from Panda Video.
        custom_referer: The 'X-Custom-Referer' value required by the server.

    Returns:
        The m3u8 Playlist object for the highest quality stream, or None if failed.
    """
    try:
        m3u8_url = convert_panda_video_url(embed_url)
        print(f"▶️ Converted to M3U8 URL: {m3u8_url}")
    except ValueError as e:
        print(f"❌ Error: {e}")
        return None

    parsed_m3u8_url = urlparse(m3u8_url)
    parsed_embed_url = urlparse(embed_url)

    headers = {
        'Host': parsed_m3u8_url.netloc,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0',
        'Accept': '*/*',
        'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Referer': f"{parsed_embed_url.scheme}://{parsed_embed_url.netloc}/",
        'X-Custom-Referer': custom_referer,
        'Origin': f"{parsed_embed_url.scheme}://{parsed_embed_url.netloc}",
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
    }
    
    with requests.Session() as session:
        session.headers.update(headers)
        try:
            print("📡 Fetching master playlist...")
            response = session.get(m3u8_url, timeout=10)
            response.raise_for_status()
            print("✅ Playlist fetched successfully.")
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch playlist: {e}")
            return None

    m3u8_obj = m3u8.loads(response.text, uri=m3u8_url)

    if not m3u8_obj.is_variant:
        print("ℹ️ This is not a variant playlist; it's the only stream available.")
        return m3u8_obj

    sorted_playlists = sorted(
        m3u8_obj.playlists,
        key=lambda p: p.stream_info.resolution[1] if p.stream_info.resolution else 0,
        reverse=True
    )

    if not sorted_playlists:
        print("❌ No streams could be found in the playlist.")
        return None

    return sorted_playlists[0]

def get_hotmart_video_url(player_url: str, session: requests.Session, course_url: str):
    """
    Extracts the video URL from a Hotmart embed player page.

    Args:
        player_url: The URL of the Hotmart embed page.
        session: The authenticated requests session to use its cookies.
        course_url: The URL of the main course page to use as a Referer.

    Returns:
        The direct video URL string, or None if not found.
    """
    print(f"-----> Acessando a página do player Hotmart: {player_url}")
    try:
        embed_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Referer': course_url,
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'iframe',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
        }
        
        response = session.get(player_url, headers=embed_headers, timeout=20)
        response.raise_for_status()
        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')
        next_data_script = soup.find('script', id='__NEXT_DATA__')

        if not next_data_script:
            print("-----> ❌ Não foi possível encontrar a tag de dados '__NEXT_DATA__' na página.")
            # with open("hotmart_error_page.html", "w", encoding="utf-8") as f:
            #     f.write(html_content)
            return None

        data = json.loads(next_data_script.string)
        media_assets = data.get('props', {}).get('pageProps', {}).get('applicationData', {}).get('mediaAssets', [])

        if not media_assets:
            print("-----> ❌ 'mediaAssets' não encontrado no JSON extraído da tag '__NEXT_DATA__'.")
            return None

        hls_asset = next((asset for asset in media_assets if 'm3u8' in asset.get('url', '')), None)
        
        video_url = None
        if hls_asset:
            video_url = hls_asset.get('url')
        elif media_assets:
            video_url = media_assets[0].get('url')
            
        if video_url:
            print("-----> ✅ URL do vídeo extraído com sucesso!")
            return video_url
        else:
            print("-----> ❌ URL não encontrada dentro de 'mediaAssets'.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao acessar a página do player Hotmart: {e}")
        return None
    except (IndexError, KeyError, TypeError, json.JSONDecodeError) as e:
        print(f"❌ Erro ao processar os dados do player: {e}")
        return None

def download_video(video_url: str, lesson_path: pathlib.Path, video_title: str, session: requests.Session, http_headers: dict = None):
    """
    Downloads a video from any supported URL using yt-dlp, passing the correct referer.
    """
    import tempfile
    import os
    
    ydl_opts = {
        'outtmpl': str(lesson_path / f'{video_title}.%(ext)s'),
        'http_headers': http_headers or {},
        'nocheckcertificate': True,
        'concurrent_fragment_downloads': 8,
        'retries': 10,
        'fragment_retries': 10,
        'quiet': True,
        'progress': True,
        'no_warnings': True,
    }

    cookie_file_path = None
    if session.cookies:
        try:
            cookie_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
            cookie_file_path = cookie_file.name
            
            cookie_file.write("# Netscape HTTP Cookie File\n")
            for cookie in session.cookies:
                # Format: domain	flag	path	secure	expiration	name	value
                domain = cookie.domain or ''
                if domain.startswith('.'):
                    flag = 'TRUE'
                else:
                    flag = 'FALSE'
                path = cookie.path or '/'
                secure = 'TRUE' if cookie.secure else 'FALSE'
                expires = str(int(cookie.expires)) if cookie.expires else '0'
                
                cookie_file.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{cookie.name}\t{cookie.value}\n")
            
            cookie_file.close()
            ydl_opts['cookiefile'] = cookie_file_path
            
        except Exception as e:
            print(f"-----> ⚠️ Aviso: Erro ao criar arquivo de cookies: {e}")

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        print("-----> ✅ Download concluído.")
        return True
    except Exception as e:
        print(f"\n❌ Erro durante o download com yt-dlp: {e}")
        return False
    finally:
        # Clean up the temporary cookie file
        if cookie_file_path and os.path.exists(cookie_file_path):
            try:
                os.unlink(cookie_file_path)
            except:
                pass

def download_attachment(session: requests.Session, url: str, save_path: pathlib.Path, name: str):
    """Downloads an attachment file."""
    print(f"      -> Baixando anexo: {name}")
    try:
        response = session.get(url, stream=True)
        response.raise_for_status()
        
        sanitized_name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
        file_extension = pathlib.Path(urlparse(url).path).suffix or '.pdf'
        file_path = save_path / f"{sanitized_name}{file_extension}"

        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"      -> Anexo salvo: {file_path.name}")
    except requests.exceptions.RequestException as e:
        print(f"      -> ❌ Falha ao baixar o anexo {name}: {e}")

def main() -> None:
    """
    Main function of the astronmembers platform downloader application.
    """
    print("🚀 === Kurseduka-dl ===")
    print('Este é um aplicativo mínimo para download de cursos da plataforma Astronmembers (https://www.astronmembers.com.br)')
    print('Seu autor é o @katomaro (Telegram e Discord), seu guia de uso (altamente recomendado visitar) pode ser encontrado em: https://katomart.com/astrok.html')
    print('Lembrando, todos os aplicativos mínimos dispostos em katomart.com são melhor elaborados na suíte completa que está em construção.')
    print("=" * 60)
    
    platform_url = request_platform_url()
    base_url = platform_url.rsplit('/', 1)[0]
    
    credentials = request_credentials()
    
    if not validate_configuration(platform_url, credentials):
        print("\n❌ Configuração cancelada pelo usuário.")
        return
    
    print("\n✅ Configuração concluída! Iniciando processo de download...")
    
    download_session = create_authenticated_session(platform_url, credentials)
    if not download_session:
        print("\n❌ Falha ao criar sessão de download.")
        return
    
    print("\n✅ Sessão de download criada com sucesso! Listando cursos...")

    courses = get_course_list(download_session, base_url)
    if courses is None or not courses:
        print("\n❌ Nenhum curso encontrado ou falha ao buscar a lista de cursos.")
        return
        
    print("\n--- Cursos Disponíveis ---")
    print("0. Baixar Todos os Cursos")
    for i, course in enumerate(courses, 1):
        print(f"{i}. {course['title']}")
    
    courses_to_process = []
    while True:
        try:
            course_index_str = input("\nDigite o número do curso que deseja processar (ou 0 para TODOS): ")
            course_index = int(course_index_str)
            
            if course_index == 0:
                courses_to_process = courses
                print("\n✅ Todos os cursos foram selecionados para download.")
                break
            elif 1 <= course_index <= len(courses):
                selected_course = courses[course_index - 1]
                courses_to_process.append(selected_course)
                print(f"\n✅ Curso selecionado: {selected_course['title']}")
                break
            else:
                print(f"❌ Número inválido. Por favor, digite um número entre 0 e {len(courses)}.")
        except ValueError:
            print("\n❌ Por favor, digite um número válido.")
            continue
    
    for course_to_download in courses_to_process:
        print("-" * 60)
        print(f"🚀 Iniciando processamento para o curso: {course_to_download['title']}")
        
        course_structure = get_course_details(download_session, course_to_download['url'])

        if course_structure:
            course_title_sanitized = re.sub(r'[\\/*?:"<>|]', "", course_to_download['title']).strip()
            download_path = pathlib.Path("download") / course_title_sanitized
            print(f'-> Baixando o curso "{course_to_download["title"]}" para a pasta "{download_path}"')
            download_path.mkdir(parents=True, exist_ok=True)

            for m_idx, module in enumerate(course_structure['modules'], 1):
                module_title_sanitized = re.sub(r'[\\/*?:"<>|]', "", module['module_title']).strip()
                module_path = download_path / f"{m_idx:02d}. {module_title_sanitized}"
                module_path.mkdir(parents=True, exist_ok=True)
                print(f'--> Módulo {m_idx}: {module["module_title"]}')

                for l_idx, lesson in enumerate(module['lessons'], 1):
                    lesson_title_sanitized = re.sub(r'[\\/*?:"<>|]', "", lesson['title']).strip()
                    lesson_path = module_path / f"{l_idx:03d}. {lesson_title_sanitized}"
                    lesson_path.mkdir(parents=True, exist_ok=True)
                    print(f'---> Aula {l_idx}: {lesson["title"]} ({lesson["url"]})')
                    
                    lesson_content = get_lesson_content(download_session, lesson['url'])

                    if not lesson_content:
                        print(f'-----> ❌ Nao foi possivel obter o conteudo da aula.')
                        continue

                    if lesson_content.get('description'):
                        description_path = lesson_path / "Descrição.html"
                        with open(description_path, 'w', encoding='utf-8') as f:
                            f.write(lesson_content['description'])
                        print(f'-----> ✅ Descrição da aula salva.')

                    player_url = lesson_content.get('player_url')

                    if player_url:
                        sanitized_video_title = 'Aula'
                        video_to_download_url = None
                        download_headers = None

                        existing_video_files = list(lesson_path.glob(f"{sanitized_video_title}.*"))
                        if existing_video_files:
                            print(f"-----> ⏭️ Vídeo já existe, pulando: {existing_video_files[0].name}")
                        else:
                            if 'pandavideo' in player_url:
                                try:
                                    video_to_download_url = convert_panda_video_url(player_url)
                                    download_headers = {'Referer': player_url}
                                except ValueError as e:
                                    print(f"-----> ❌ Erro ao converter URL do Panda: {e}")
                            
                            elif 'play.hotmart.com' in player_url:
                                video_to_download_url = get_hotmart_video_url(player_url, download_session, lesson['url'])
                                download_headers = {
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0',
                                    'Accept': '*/*',
                                    'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
                                    'Origin': 'https://cf-embed.play.hotmart.com',
                                    'Referer': player_url,
                                    'Connection': 'keep-alive',
                                    'Sec-Fetch-Dest': 'empty',
                                    'Sec-Fetch-Mode': 'cors',
                                    'Sec-Fetch-Site': 'same-site',
                                }
                                
                            elif 'youtube.com' in player_url or 'vimeo.com' in player_url:
                                video_to_download_url = player_url
                                download_headers = {'Referer': base_url}
                            
                            if video_to_download_url:
                                print(f"-----> 🎬 Baixando vídeo...")
                                download_video(video_to_download_url, lesson_path, sanitized_video_title, download_session, http_headers=download_headers)
                            else:
                                print(f"-----> ⚠️ Player não suportado ou falha ao extrair URL de: {player_url}")
                    else:
                        print('-----> ℹ️ Nenhum player de vídeo encontrado nesta aula.')
                        
                    if lesson_content.get('attachments'):
                        print('-----> 📎 Verificando anexos...')
                        for attachment in lesson_content['attachments']:
                            sanitized_name = re.sub(r'[\\/*?:"<>|]', "", attachment['name']).strip()
                            file_extension = pathlib.Path(urlparse(attachment['url']).path).suffix or '.pdf'
                            attachment_filename = f"{sanitized_name}{file_extension}"
                            attachment_path = lesson_path / attachment_filename
                            
                            if attachment_path.exists():
                                print(f"      -> ⏭️ Anexo já existe, pulando: {attachment_filename}")
                            else:
                                download_attachment(download_session, attachment['url'], lesson_path, attachment['name'])
        else:
            print(f"\n❌ Não foi possível obter a estrutura do curso: {course_to_download['title']}")

    print("\n🎉 Processo de download concluído para os cursos selecionados!")


if __name__ == "__main__":
    main()