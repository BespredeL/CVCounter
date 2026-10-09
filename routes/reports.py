# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 03.12.2025
# Updated: 29.07.2026
# Website: https://bespredel.name

import json
import mimetypes
from threading import Thread

from flask import Blueprint, abort, render_template, request, send_file
from markupsafe import escape

from system.utils.app_context import get_app_context
from system.utils.i18n import trans as translate
from system.utils.saved_media import (
    ensure_web_playable_video,
    count_saved_images,
    count_saved_recordings,
    list_saved_images,
    list_saved_recordings,
    resolve_saved_image,
    resolve_saved_recording,
    resolve_video_poster,
    warm_web_videos,
)
from system.utils.validators import ValidationError, validate_report_list_request

reports_bp = Blueprint('reports', __name__)


def _valid_location(location: str | None) -> str:
    """
    Validate the location.
    
    Args:
        location (str | None): The location to validate
    
    Returns:
        str: The validated location
    """
    context = get_app_context()
    locations = context['locations']
    if location is None:
        abort(404, translate('Page not found'))
    location = str(location).strip()
    if location not in locations:
        abort(404, translate('Page not found'))
    return location


def _start_media_warm(location: str, config) -> None:
    """
    Pre-convert newest recordings in the background so Play is faster.
    
    Args:
        location (str): The location to warm
        config: The configuration
    
    Returns:
        None
    """
    thread = Thread(
        target=warm_web_videos,
        kwargs={'location': location, 'config': config, 'limit': 3},
        name=f'warm-web-videos-{location}',
        daemon=True,
    )
    thread.start()


@reports_bp.route('/reports')
def reports() -> str:
    """
    Display the main reports page with locations overview and metrics.

    Returns:
        str: Rendered HTML template with reports overview
    """
    context = get_app_context()
    locations_dict = context['locations_dict']
    db_manager = context['db_manager']
    config = context['config']
    active_counters = context.get('object_counters', {})

    locations_stats = {}
    total_all_sessions = 0
    total_all_images = 0
    total_all_videos = 0

    for loc_key, loc_title in locations_dict.items():
        paginated = db_manager.get_paginated(loc_key, page=1, per_page=1)
        loc_reports = paginated['total'] if paginated else 0
        loc_images = count_saved_images(loc_key, config=config)
        loc_videos = count_saved_recordings(loc_key, config=config)
        is_active = loc_key in active_counters

        locations_stats[loc_key] = {
            'title': loc_title,
            'reports_count': loc_reports,
            'images_count': loc_images,
            'videos_count': loc_videos,
            'is_active': is_active,
        }
        total_all_sessions += loc_reports
        total_all_images += loc_images
        total_all_videos += loc_videos

    return render_template(
        'reports/index.html',
        object_counters=locations_dict,
        locations_stats=locations_stats,
        total_all_sessions=total_all_sessions,
        total_all_images=total_all_images,
        total_all_videos=total_all_videos,
    )


@reports_bp.route('/reports/<string:location>')
def report_list(location: str = None) -> str:
    """
    Display paginated list of reports for a specific location.

    Args:
        location (str): The identifier for the detection location

    Returns:
        str: Rendered HTML template with paginated reports list
    """
    context = get_app_context()
    locations_dict = context['locations_dict']
    db_manager = context['db_manager']
    config = context['config']
    active_counters = context.get('object_counters', {})

    try:
        location = _valid_location(location)

        validated_data = validate_report_list_request()
        r_page = validated_data['page']
        per_page = 10

        pagination = db_manager.get_paginated(location, r_page, per_page)

        if pagination is None:
            abort(404, translate('Page not found'))

        items = pagination['results']
        current_page = pagination['page']
        total_items = pagination['total']
        total_pages = (total_items + per_page - 1) // per_page

        try:
            images_page = int(request.args.get('images_page', 1) or 1)
        except (ValueError, TypeError):
            images_page = 1
        try:
            videos_page = int(request.args.get('videos_page', 1) or 1)
        except (ValueError, TypeError):
            videos_page = 1
        images_page = max(1, images_page)
        videos_page = max(1, videos_page)

        media_tab = (request.args.get('media_tab') or 'images').strip().lower()
        if media_tab not in ('images', 'videos'):
            media_tab = 'images'

        images_per_page = 24
        videos_per_page = 12

        total_images = count_saved_images(location, config=config)
        total_videos = count_saved_recordings(location, config=config)

        images_total_pages = (total_images + images_per_page - 1) // images_per_page if total_images else 1
        videos_total_pages = (total_videos + videos_per_page - 1) // videos_per_page if total_videos else 1

        images_page = min(images_page, images_total_pages) if total_images else 1
        videos_page = min(videos_page, videos_total_pages) if total_videos else 1

        images_offset = (images_page - 1) * images_per_page
        videos_offset = (videos_page - 1) * videos_per_page

        saved_images = list_saved_images(location, config=config, limit=images_per_page, offset=images_offset)
        saved_recordings = list_saved_recordings(location, config=config, limit=videos_per_page, offset=videos_offset)
        if total_videos:
            _start_media_warm(location, config)

        # Page-level stats summary
        page_total_count = sum(item.total_count or 0 for item in items)
        page_defects_count = sum(item.defects_count or 0 for item in items)
        page_correct_count = sum(item.correct_count or 0 for item in items)
        page_source_count = sum(item.source_count or 0 for item in items)
        is_counter_active = location in active_counters

        return render_template(
            'reports/list.html',
            object_counters=locations_dict,
            items=items,
            location=location,
            current_page=current_page,
            total_pages=total_pages,
            saved_images=saved_images,
            saved_recordings=saved_recordings,
            images_total_items=total_images,
            videos_total_items=total_videos,
            images_current_page=images_page,
            images_total_pages=images_total_pages,
            videos_current_page=videos_page,
            videos_total_pages=videos_total_pages,
            media_tab=media_tab,
            page_total_count=page_total_count,
            page_defects_count=page_defects_count,
            page_correct_count=page_correct_count,
            page_source_count=page_source_count,
            is_counter_active=is_counter_active,
            json=json
        )
    except ValidationError as e:
        abort(400, str(e))
    except Exception as e:
        from system.utils.logger import Logger
        Logger().error(f"Error in report_list: {e}")
        abort(500, "Internal server error")


@reports_bp.route('/reports/<string:location>/media/image/<path:filename>')
def report_media_image(location: str, filename: str):
    """
    Serve a saved capture image for the location.
    
    Args:
        location (str): The location to serve the image for
        filename (str): The filename of the image to serve
    
    Returns:
        str: The served image
    """
    location = _valid_location(location)
    config = get_app_context()['config']
    path = resolve_saved_image(location, filename, config=config)
    if path is None:
        abort(404, translate('Page not found'))
    mime, _ = mimetypes.guess_type(str(path))
    return send_file(path, mimetype=mime or 'image/jpeg', conditional=True, max_age=3600)


@reports_bp.route('/reports/<string:location>/media/video/<path:filename>/poster')
def report_media_video_poster(location: str, filename: str):
    """
    Serve a JPEG poster frame for a saved recording.
    
    Args:
        location (str): The location to serve the poster for
        filename (str): The filename of the recording to serve the poster for
    
    Returns:
        str: The served poster
    """
    location = _valid_location(location)
    config = get_app_context()['config']
    path = resolve_video_poster(location, filename, config=config)
    if path is None:
        abort(404, translate('Page not found'))
    return send_file(path, mimetype='image/jpeg', conditional=True, max_age=86400)


@reports_bp.route('/reports/<string:location>/media/video/<path:filename>')
def report_media_video(location: str, filename: str):
    """
    Serve a saved recording (browser-playable when possible).
    
    Args:
        location (str): The location to serve the recording for
        filename (str): The filename of the recording to serve
    
    Returns:
        str: The served recording
    """
    location = _valid_location(location)
    config = get_app_context()['config']
    path = resolve_saved_recording(location, filename, config=config)
    if path is None:
        abort(404, translate('Page not found'))

    as_attachment = request.args.get('download') in ('1', 'true', 'yes')
    if as_attachment:
        mime, _ = mimetypes.guess_type(str(path))
        return send_file(
            path,
            mimetype=mime or 'video/mp4',
            as_attachment=True,
            download_name=path.name,
            conditional=True,
            max_age=0,
        )

    playable = ensure_web_playable_video(path, location)
    mime, _ = mimetypes.guess_type(str(playable))
    if not mime:
        mime = 'video/webm' if playable.suffix.lower() == '.webm' else 'video/mp4'
    return send_file(
        playable,
        mimetype=mime,
        conditional=True,
        max_age=3600,
    )


@reports_bp.route('/reports/<string:location>/<int:report_id>')
def report_show(location: str, report_id: int) -> str:
    """
    Display detailed view of a specific report.

    Args:
        location (str): The identifier for the detection location
        report_id (int): The report ID

    Returns:
        str: Rendered HTML template with report details
    """
    context = get_app_context()
    db_manager = context['db_manager']

    counter = db_manager.get_count(report_id)

    if counter is None:
        abort(404, translate('Page not found'))

    location = str(location).strip()
    if counter.location != location:
        abort(404, translate('Page not found'))

    prev_report_id = None
    next_report_id = None
    session = db_manager.create_session()
    try:
        from system.db.models.cvcounter import CVCounter
        prev_row = session.query(CVCounter.id).filter(
            CVCounter.location == location,
            CVCounter.id < report_id
        ).order_by(CVCounter.id.desc()).first()
        if prev_row:
            prev_report_id = prev_row[0]

        next_row = session.query(CVCounter.id).filter(
            CVCounter.location == location,
            CVCounter.id > report_id
        ).order_by(CVCounter.id.asc()).first()
        if next_row:
            next_report_id = next_row[0]
    except Exception:
        pass
    finally:
        session.close()

    is_counter_active = location in context.get('object_counters', {})

    return render_template(
        'reports/show.html',
        location=location,
        counter=counter,
        prev_report_id=prev_report_id,
        next_report_id=next_report_id,
        is_counter_active=is_counter_active,
        json=json
    )
