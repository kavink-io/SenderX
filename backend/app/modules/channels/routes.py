from flask import Blueprint, jsonify

from app.modules.channels.service import ChannelService


channels_bp = Blueprint("channels", __name__)


@channels_bp.route("/", methods=["GET"])
def get_channels():

    channels = ChannelService.get_all_channels()

    return jsonify({
        "success": True,
        "message": "Channels retrieved successfully",
        "data": channels
    }), 200


@channels_bp.route("/<string:channel_name>", methods=["GET"])
def get_channel(channel_name):

    channel = ChannelService.get_channel(channel_name)

    if not channel:
        return jsonify({
            "success": False,
            "message": "Unsupported communication channel",
            "data": None
        }), 404

    return jsonify({
        "success": True,
        "message": "Channel retrieved successfully",
        "data": channel
    }), 200