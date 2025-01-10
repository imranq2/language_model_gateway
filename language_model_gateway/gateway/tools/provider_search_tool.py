import os
from typing import Optional, Dict, Any, List, cast, Type, Literal, Tuple

import httpx
from langchain.tools import BaseTool
from pydantic import BaseModel, Field


class ProviderSearchToolInput(BaseModel):
    search: Optional[str] = Field(description="Search query to find providers")
    lat: Optional[float] = Field(description="Latitude of the search location")
    lon: Optional[float] = Field(description="Longitude of the search location")
    distance: Optional[float] = Field(description="Search radius in miles")
    specialty: Optional[List[str]] = Field(
        description="List of specialties to filter by"
    )
    insurance: Optional[List[str]] = Field(
        description="List of insurance plans to filter by"
    )


class ProviderSearchTool(BaseTool):
    name: str = "provider_search"
    description: str = (
        "Search for healthcare providers (e.g., doctors, clinics and hospitals) based on various criteria like name, specialty, location, insurance etc."
    )
    args_schema: Type[BaseModel] = ProviderSearchToolInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    api_url: Optional[str] = os.environ.get("PROVIDER_SEARCH_API_URL")

    # noinspection PyMethodMayBeStatic
    def _build_query(self) -> str:
        return """
            query SearchProviders(
                $search: String
                $searchPosition: SearchPosition
                $specialty: [InputCoding]
                $insurance: [InputCoding]
            ) {
                providers(
                    client: [
                        {
                            id: lee_health
                            data_sets: nppes
                        }
                    ]
                    search: $search
                    search_position: $searchPosition
                    specialty: $specialty
                    insurance: $insurance
                ) {
                    total_count
                    results {
                        id
                        npi
                        content
                        name {
                            text
                            family
                            given
                        }
                        specialty {
                            code
                            system
                            display
                            isPrimary
                        }
                        location {
                            name
                            address {
                                text
                                line
                                city
                                state
                                postalCode
                            }
                            position {
                                lat
                                lon
                            }
                            telecom {
                                system
                                value
                            }
                        }
                        next_available_slot {
                            start
                            end
                            minutesDuration
                        }
                        bookable {
                            online
                            phone
                        }
                        insurance_plan {
                            name
                        }
                        endpoint {
                            name
                        }
                    }
                }
            }
        """

    # noinspection PyMethodMayBeStatic
    def _prepare_variables(
        self,
        search: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        distance: Optional[float] = None,
        specialty: Optional[List[str]] = None,
        insurance: Optional[List[str]] = None,
    ) -> Dict[str, Any]:

        variables: Dict[
            str, str | float | int | Dict[str, Any] | List[Dict[str, Any]] | None
        ] = {
            "search": search,
        }

        if lat is not None and lon is not None:
            variables["searchPosition"] = {
                "lat": lat,
                "lon": lon,
                "distance": distance or 50,  # default 50 mile radius
            }

        if specialty:
            variables["specialty"] = [{"display": spec} for spec in specialty]

        if insurance:
            variables["insurance"] = [{"display": ins} for ins in insurance]

        return variables

    def _prepare_request_payload(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        return {"query": self._build_query(), "variables": variables}

    # noinspection PyMethodMayBeStatic
    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Process and validate the API response"""
        if response.status_code != 200:
            raise Exception(
                f"API request failed with status {response.status_code}: {response.text}"
            )

        data = response.json()

        if "errors" in data:
            raise Exception(f"GraphQL query failed: {data['errors']}")

        return cast(Dict[str, Any], data["data"])

    def _run(
        self,
        search: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        distance: Optional[float] = None,
        specialty: Optional[List[str]] = None,
        insurance: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Synchronous execution"""
        raise NotImplementedError("Use async version of this tool")

    async def _arun(
        self,
        search: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        distance: Optional[float] = None,
        specialty: Optional[List[str]] = None,
        insurance: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, Any], str]:
        """Asynchronous execution"""

        assert self.api_url, "API URL is required"

        variables = self._prepare_variables(
            search=search,
            lat=lat,
            lon=lon,
            distance=distance,
            specialty=specialty,
            insurance=insurance,
        )

        payload = self._prepare_request_payload(variables)

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "accept": "*/*",
        }

        async_client: httpx.AsyncClient = httpx.AsyncClient(headers=headers)

        try:
            response = await async_client.post(self.api_url, json=payload, timeout=30.0)
            return (
                self._handle_response(response),
                f"ProviderSearchAgent: Searched for {search} {variables} ",
            )

        except httpx.TimeoutException:
            raise Exception("Request timed out")
        except httpx.RequestError as e:
            raise Exception(f"Request failed: {str(e)}")
