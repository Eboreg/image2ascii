import { TrackedObject } from "tracked-built-ins";
import Route from "@ember/routing/route";
import { service } from "@ember/service";
import type RequestManagerService from "www/services/request";
import type { BackendResponse, Flag } from "global";
import RSVP from "rsvp";
import { action } from "@ember/object";
import type Transition from "@ember/routing/transition";
import type ApplicationController from "www/controllers/application";

export interface ApplicationModel extends BackendResponse {
    flags: Flag[];
}

export default class ApplicationRoute extends Route<ApplicationModel> {
    @service declare request: RequestManagerService;

    queryParams = {
        uuid: { replace: false, refreshModel: true },
    };

    async model(params: { uuid?: string }): Promise<ApplicationModel> {
        const dataUrl = "http://localhost:8000/json" + (params.uuid ? `?uuid=${params.uuid}` : "");
        const flagsUrl = "http://localhost:8000/flags";
        const dataResponse = await this.request.request({ url: dataUrl });
        const flagsResponse = await this.request.request({ url: flagsUrl });
        const data = new TrackedObject(dataResponse.content as any) as BackendResponse;

        return RSVP.hash({
            flags: flagsResponse.content as Flag[],
            ...data,
        });
    }

    @action loading(transition: Transition) {
        const controller = this.controllerFor("application") as ApplicationController;

        controller.isLoading = true;
        transition.promise?.finally(() => {
            controller.isLoading = false;
        });
    }
}
