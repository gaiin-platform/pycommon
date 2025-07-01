# API module exports
# Copyright (c) 2024 Vanderbilt University

# Import submodules for direct access
from . import (
    amplify_groups,
    api_key,
    assistants,
    credentials,
    data_sources,
    embeddings,
    files,
    object_permissions,
    ops,
    secrets,
    ses_email,
)
from .amplify_groups import verify_member_of_ast_admin_group, verify_user_in_amp_group
from .api_key import deactivate_key, get_api_keys
from .assistants import (
    create_assistant,
    delete_assistant,
    list_assistants,
    share_assistant,
)
from .credentials import get_credentials, get_endpoint, get_json_credetials
from .data_sources import (
    extract_key,
    get_data_source_keys,
    translate_user_data_sources_to_hash_data_sources,
)
from .embeddings import check_embedding_completion, delete_embeddings
from .files import get_file_presigned_url, upload_file, upload_to_presigned_url
from .object_permissions import (
    can_access_objects,
    simulate_can_access_objects,
    update_object_permissions,
)
from .ops import api_tool, set_op_type, set_permissions_by_state, set_route_data

# Import most commonly used functions from each API module
from .secrets import (
    delete_secret_parameter,
    get_secret_parameter,
    get_secret_value,
    store_secret_parameter,
    update_dict_with_secrets,
)
from .ses_email import send_email

__all__ = [
    # Most common functions
    "get_secret_value",
    "get_secret_parameter",
    "store_secret_parameter",
    "upload_file",
    "create_assistant",
    "list_assistants",
    "get_credentials",
    "delete_embeddings",
    "extract_key",
    "update_object_permissions",
    "can_access_objects",
    "verify_member_of_ast_admin_group",
    "deactivate_key",
    "send_email",
    "api_tool",
    # All other functions
    "update_dict_with_secrets",
    "delete_secret_parameter",
    "get_file_presigned_url",
    "upload_to_presigned_url",
    "delete_assistant",
    "share_assistant",
    "get_json_credetials",
    "get_endpoint",
    "check_embedding_completion",
    "get_data_source_keys",
    "translate_user_data_sources_to_hash_data_sources",
    "simulate_can_access_objects",
    "verify_user_in_amp_group",
    "get_api_keys",
    "set_route_data",
    "set_permissions_by_state",
    "set_op_type",
    # Submodules
    "secrets",
    "files",
    "assistants",
    "credentials",
    "embeddings",
    "data_sources",
    "object_permissions",
    "amplify_groups",
    "api_key",
    "ses_email",
    "ops",
]
