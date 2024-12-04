import asyncio
import openai
from openai import OpenAI
from django.conf import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

async def get_openai_assistant_response(query, vector_store_id):
    try:
        assistant = client.beta.assistants.create(
            name="Google Meeting AI Chatbot",
            instructions=(
                "Act as a highly capable virtual assistant specifically designed for Google Meetings, "
                "where your primary responsibility is to assist users by providing comprehensive insights "
                "derived from meeting transcriptions, which include critical elements such as the identification "
                "of speaker names, the summarization of key discussion points, and the extraction of actionable "
                "items that arise during the meeting; you should accurately summarize the content discussed, "
                "ensuring that important information is highlighted and easily accessible, while also being "
                "prepared to answer any questions related to the discussions that took place during the meeting, "
                "utilizing the transcription data to generate concise yet informative summaries and detailed "
                "explanations when users seek clarification on specific topics discussed; throughout this process, "
                "it is essential to prioritize user engagement and maintain a smooth conversational flow, ensuring "
                "that users feel supported and informed in navigating the complexities of their meetings."
            ),
            tools=[
                {"type": "file_search"},
                {"type": "code_interpreter"}
            ],
            tool_resources={"file_search": {"vector_store_ids": [vector_store_id]}},
            model="gpt-4-turbo-preview",
        )

        thread = client.beta.threads.create()
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=query
        )
        run = client.beta.threads.runs.create(thread_id=thread.id, assistant_id=assistant.id)

        while run.status != "completed":
            await asyncio.sleep(1)
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

        messages = client.beta.threads.messages.list(thread_id=thread.id)
        openai_response = messages.data[0].content[0].text.value if messages.data else "No response"

        return openai_response
    except openai.APIError as openai_error:
        print(f"OpenAI API error: {openai_error}", exc_info=True)
        raise
    except Exception as e:
        print(f"General error while getting OpenAI response: {e}", exc_info=True)
        raise
