from fastapi import APIRouter, FastAPI, Depends,UploadFile, status, Request
from fastapi.responses import JSONResponse, FileResponse
import os
from ..help.config import get_settings , Settings
from ..controllers import DataController, ProjectController , ProcessController
import aiofiles
from ..models import ResponseSignal
import logging
from .schemes.data import ProcessRequest
from ..models.ProjectModel import ProjectModel
from ..models.ChunkModel import ChunkModel
from ..models.AssetModel import AssetModel
from ..models.db_schemes import DataChunk, Asset
from ..models.enums.AssetTypeEnum import AssetTypeEnum
from ..controllers import NLPController
from ..models.db_schemes import DataChunk
from datetime import datetime 

logger = logging.getLogger("uvicorn.error")

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1","data"]
)

@data_router.post("/upload/{project_id}")
async def upload_data(request: Request, project_id: str, file: UploadFile,
                      app_settings: Settings = Depends(get_settings)):
        
    
    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    # validate the file properties
    data_controller = DataController()

    is_valid, result_signal = data_controller.validate_uploaded_file(file=file)

    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": result_signal
            }
        )

    project_dir_path = ProjectController().get_project_path(project_id=project_id)
    file_path, file_id = data_controller.generate_unique_filepath(
        orig_file_name=file.filename,
        project_id=project_id
    )

    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)
    except Exception as e:

        logger.error(f"Error while uploading file: {e}")

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseSignal.FILE_UPLOAD_FAILED.value
            }
        )

    # store the assets into the database
    asset_model = await AssetModel.create_instance(
        db_client=request.app.db_client
    )

    asset_resource = Asset(
        asset_project_id=project.id,
        asset_type=AssetTypeEnum.FILE.value,
        asset_name=file_id,
        asset_size=os.path.getsize(file_path)
    )

    asset_record = await asset_model.create_asset(asset=asset_resource)

    return JSONResponse(
            content={
                "signal": ResponseSignal.FILE_UPLOAD_SUCCESS.value,
                "file_id": str(asset_record.id),
                "asset_name": asset_record.asset_name,
            }
        )

@data_router.post("/process/{project_id}")
async def process_endpoint(request: Request, project_id: str, process_request: ProcessRequest):

    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset

    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    asset_model = await AssetModel.create_instance(
            db_client=request.app.db_client
        )

    project_files_ids = {}
    if process_request.file_id:
        asset_record = await asset_model.get_asset_record(
            asset_project_id=project.id,
            asset_name=process_request.file_id
        )

        if asset_record is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseSignal.FILE_ID_ERROR.value,
                }
            )

        project_files_ids = {
            asset_record.id: asset_record.asset_name
        }
    
    else:
        

        project_files = await asset_model.get_all_project_assets(
            asset_project_id=project.id,
            asset_type=AssetTypeEnum.FILE.value,
        )

        project_files_ids = {
            record.id: record.asset_name
            for record in project_files
        }

    if len(project_files_ids) == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseSignal.NO_FILES_ERROR.value,
            }
        )
    
    process_controller = ProcessController(project_id=project_id)

    no_records = 0
    no_files = 0

    chunk_model = await ChunkModel.create_instance(
                        db_client=request.app.db_client
                    )

    if do_reset == 1:
        _ = await chunk_model.delete_chunks_by_project_id(
            project_id=project.id
        )

    for asset_id, file_id in project_files_ids.items():

        file_content = process_controller.get_file_content(file_id=file_id)

        if file_content is None:
            logger.error(f"Error while processing file: {file_id}")
            continue

        file_chunks = process_controller.process_file_content(
            file_content=file_content,
            file_id=file_id,
            chunk_size=chunk_size,
            overlap_size=overlap_size
        )

        if file_chunks is None or len(file_chunks) == 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseSignal.PROCESSING_FAILED.value
                }
            )

        file_chunks_records = [
            DataChunk(
                chunk_text=chunk.page_content,
                chunk_metadata=chunk.metadata,
                chunk_order=i+1,
                chunk_project_id=project.id,
                chunk_asset_id=asset_id
            )
            for i, chunk in enumerate(file_chunks)
        ]

        no_records += await chunk_model.insert_many_chunks(chunks=file_chunks_records)
        no_files += 1

    return JSONResponse(
        content={
            "signal": ResponseSignal.PROCESSING_SUCCESS.value,
            "inserted_chunks": no_records,
            "processed_files": no_files
        }
    )


@data_router.delete("/delete/{project_id}/{asset_name}")
async def delete_asset(request: Request, project_id: str, asset_name: str):

    # Step 1: Get the project
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    # Step 2: Find the asset to ensure it exists and belongs to the project
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    asset_to_delete = await asset_model.get_asset_record(
        asset_project_id=project.id,
        asset_name=asset_name
    )

    if asset_to_delete is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"signal": ResponseSignal.FILE_ID_ERROR.value}
        )

    # Note: We are not deleting vectors from Qdrant yet as it requires a more complex setup
    # to track vector IDs associated with each asset. This can be a future enhancement.

    # Step 3: Delete chunks from MongoDB
    chunk_model = await ChunkModel.create_instance(db_client=request.app.db_client)
    await chunk_model.delete_chunks_by_asset_id(asset_id=asset_to_delete.id)

    # Step 4: Delete the physical file from the server
    data_controller = DataController()
    data_controller.delete_physical_file(project_id=project_id, file_name=asset_to_delete.asset_name)

    # Step 5: Delete the asset record from MongoDB
    is_deleted = await asset_model.delete_asset(asset_id=asset_to_delete.id)

    if not is_deleted:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.FILE_DELETE_FAILED.value}
        )
    
    # Step 6: Auto re-index the entire project
    if is_deleted:
        nlp_controller = NLPController(
            vectordb_client=request.app.vectordb_client,
            generation_client=request.app.generation_client,
            embedding_client=request.app.embedding_client,
            sparse_embedding_client=request.app.sparse_embedding_client, 
            reranker_client=request.app.reranker_client,
            template_parser=request.app.template_parser,
        )
        await nlp_controller.reindex_project(project=project, chunk_model=chunk_model)


    return JSONResponse(
        content={
            "signal": ResponseSignal.FILE_DELETED_SUCCESSFULLY.value,
            "deleted_asset_name": asset_to_delete.asset_name,
            "message": "File deleted and project automatically re-indexed."
        }
    )


# @data_router.get("/assets/{project_id}")
# async def get_assets(request: Request, project_id: str):
#     project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
#     project = await project_model.get_project_or_create_one(project_id=project_id)

#     if project is None:
#         return JSONResponse(status_code=404, content={"signal": "PROJECT_NOT_FOUND"})

#     asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
#     assets = await asset_model.get_all_project_assets(
#         asset_project_id=project.id,
#         asset_type=AssetTypeEnum.FILE.value
#     )

#     # Convert ObjectId to string for JSON serialization
#     assets_list = [asset.dict() for asset in assets]
#     for asset_data in assets_list:
#         asset_data['id'] = str(asset_data['id'])
#         asset_data['asset_project_id'] = str(asset_data['asset_project_id'])

#     return JSONResponse(
#         content={
#             "signal": "ASSETS_RETRIEVED_SUCCESSFULLY",
#             "assets": assets_list
#         }
#     )

# @data_router.get("/assets/{project_id}")
# async def get_assets(request: Request, project_id: str):
#     # Step 1: Get the project
#     project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
#     project = await project_model.get_project_or_create_one(project_id=project_id)

#     if project is None:
#         return JSONResponse(
#             status_code=status.HTTP_404_NOT_FOUND,
#             content={"signal": ResponseSignal.PROJECT_NOT_FOUND_ERROR.value}
#         )

#     # Step 2: Get all assets for the project
#     asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
#     assets = await asset_model.get_all_project_assets(
#         asset_project_id=project.id,
#         asset_type=AssetTypeEnum.FILE.value
#     )

#     # Step 3: Manually serialize the assets to be JSON-safe
#     assets_list = []
#     for asset in assets:
#         asset_data = asset.dict()
#         # Convert ObjectId and datetime to string to ensure JSON compatibility
#         asset_data['_id'] = str(asset_data.get('_id'))
#         asset_data['asset_project_id'] = str(asset_data.get('asset_project_id'))
#         asset_data['asset_pushed_at'] = asset_data.get('asset_pushed_at').isoformat()
#         assets_list.append(asset_data)

#     return JSONResponse(
#         content={
#             "signal": "ASSETS_RETRIEVED_SUCCESSFULLY",
#             "assets": assets_list
#         }
#     )


@data_router.get("/assets/{project_id}")
async def get_assets(request: Request, project_id: str):
    # ... (الكود الخاص بجلب المشروع يبقى كما هو)
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    if project is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"signal": ResponseSignal.PROJECT_NOT_FOUND_ERROR.value}
        )

    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    assets = await asset_model.get_all_project_assets(
        asset_project_id=project.id,
        asset_type=AssetTypeEnum.FILE.value
    )

    # الكود الجديد والأكثر أمانًا للمعالجة
    assets_list = []
    for asset in assets:
        asset_data = asset.dict()

        # تحويل آمن لمعرفات MongoDB
        if asset_data.get('_id'):
            asset_data['_id'] = str(asset_data.get('_id'))
        if asset_data.get('id'):
            asset_data['id'] = str(asset_data.get('id'))
        if asset_data.get('asset_project_id'):
            asset_data['asset_project_id'] = str(asset_data.get('asset_project_id'))

        # تحويل آمن للتاريخ (هذا هو الجزء الأهم)
        pushed_at = asset_data.get('asset_pushed_at')
        if isinstance(pushed_at, datetime):
            asset_data['asset_pushed_at'] = pushed_at.isoformat()
        else:
            # في حالة وجود بيانات قديمة تالفة، نضع تاريخًا افتراضيًا
            asset_data['asset_pushed_at'] = datetime.utcnow().isoformat()

        assets_list.append(asset_data)

    return JSONResponse(
        content={
            "signal": "ASSETS_RETRIEVED_SUCCESSFULLY",
            "assets": assets_list
        }
    )




@data_router.put("/update/{project_id}/{asset_name}")
async def update_asset(request: Request, project_id: str, asset_name: str, file: UploadFile,
                      app_settings: Settings = Depends(get_settings)):
    
    # Step 1: Get project
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    # Step 2: Find the asset to update
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    asset_to_update = await asset_model.get_asset_record(
        asset_project_id=project.id,
        asset_name=asset_name
    )

    if asset_to_update is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"signal": ResponseSignal.FILE_ID_ERROR.value}
        )

    # Step 3: Validate the new file
    data_controller = DataController()
    is_valid, result_signal = data_controller.validate_uploaded_file(file=file)
    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": result_signal}
        )

    # Step 4: Delete old chunks from MongoDB
    chunk_model = await ChunkModel.create_instance(db_client=request.app.db_client)
    await chunk_model.delete_chunks_by_asset_id(asset_id=asset_to_update.id)
    
    # Step 5: Overwrite the physical file
    project_dir_path = ProjectController().get_project_path(project_id=project_id)
    file_path = os.path.join(project_dir_path, asset_to_update.asset_name)

    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)
    except Exception as e:
        logger.error(f"Error while updating file: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.FILE_UPLOAD_FAILED.value}
        )
    
    # Step 6: Update the asset record in MongoDB with new size and date
    new_file_size = os.path.getsize(file_path)
    await asset_model.update_asset_record(
        asset_id=asset_to_update.id,
        new_size=new_file_size
    )

    # Step 7: Auto re-process the updated file to create new chunks
    process_controller = ProcessController(project_id=project_id)
    file_content = process_controller.get_file_content(file_id=asset_to_update.asset_name)

    if file_content:
        file_chunks = process_controller.process_file_content(
            file_content=file_content, file_id=asset_to_update.asset_name
        )
        if file_chunks:
            file_chunks_records = [
                DataChunk(
                    chunk_text=chunk.page_content, chunk_metadata=chunk.metadata,
                    chunk_order=i + 1, chunk_project_id=project.id,
                    chunk_asset_id=asset_to_update.id
                ) for i, chunk in enumerate(file_chunks)
            ]
            await chunk_model.insert_many_chunks(chunks=file_chunks_records)

    # Step 8: Auto re-index the entire project
    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        sparse_embedding_client=request.app.sparse_embedding_client, # تمت إضافته
        reranker_client=request.app.reranker_client,
        template_parser=request.app.template_parser,
    )
    inserted_count = await nlp_controller.reindex_project(project=project, chunk_model=chunk_model)



    return JSONResponse(
        content={
            "signal": ResponseSignal.FILE_UPDATED_SUCCESSFULLY.value,
            "asset_name": asset_to_update.asset_name,
            "message": f"File updated. Project automatically re-indexed with {inserted_count} total chunks."
        }
    )


@data_router.get("/projects")
async def get_all_projects(request: Request):
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    projects, _ = await project_model.get_all_projects()

    # Convert ObjectId to string for JSON serialization
    projects_list = [p.dict() for p in projects]
    for p_data in projects_list:
        p_data['id'] = str(p_data['id'])

    return JSONResponse(
        content={
            "signal": "PROJECTS_RETRIEVED_SUCCESSFULLY",
            "projects": projects_list
        }
    )



@data_router.post("/projects")
async def create_project(request: Request):
    body = await request.json()
    project_id = body.get("project_id")

    if not project_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": "PROJECT_ID_IS_REQUIRED"}
        )

    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    project_data = project.dict()
    project_data['id'] = str(project_data['id'])

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "signal": "PROJECT_CREATED_SUCCESSFULLY",
            "project": project_data
        }
    )


@data_router.delete("/projects/{project_id}")
async def delete_project(request: Request, project_id: str):

    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    chunk_model = await ChunkModel.create_instance(db_client=request.app.db_client)

    project = await project_model.get_project_or_create_one(project_id=project_id)
    if not project or not project.id:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"signal": "PROJECT_NOT_FOUND"}
        )

    data_controller = DataController()
    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        sparse_embedding_client=request.app.sparse_embedding_client, 
        reranker_client=request.app.reranker_client,
        template_parser=request.app.template_parser,
    )

    assets_to_delete = await asset_model.get_all_project_assets(asset_project_id=project.id, asset_type=AssetTypeEnum.FILE.value)
    for asset in assets_to_delete:
        data_controller.delete_physical_file(project_id=project.project_id, file_name=asset.asset_name)

    nlp_controller.reset_vector_db_collection(project=project)

    await chunk_model.delete_chunks_by_project_id(project_id=project.id)

    await asset_model.delete_assets_by_project_id(project_id=project.id)

    is_deleted = await project_model.delete_project(project_id=project.id)

    if not is_deleted:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"signal": "PROJECT_DELETION_FAILED"}
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": "PROJECT_DELETED_SUCCESSFULLY",
            "deleted_project_id": project_id
        }
    )



@data_router.get("/files/{project_id}/{asset_name}")
async def get_file_content(project_id: str, asset_name: str):
    project_controller = ProjectController()
    project_path = project_controller.get_project_path(project_id=project_id)
    file_path = os.path.join(project_path, asset_name)

    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"signal": "FILE_NOT_FOUND"})

    return FileResponse(file_path)