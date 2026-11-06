# clearops-app

Application code for ClearOps (frontend, API). This is the **app repo**.

- Jenkins builds and tests the images here, pushes them to Docker Hub
  (`crystalvivian/clearops-*`), then commits the new image tag to the
  **config repo**, [clearops-gitops](https://github.com/vivianokose/clearops-gitops).
- ArgoCD watches the config repo and deploys. Jenkins never touches the cluster.

Part of Module 12.5 (GitOps with ArgoCD) in
[nexaops-operations-lab](https://github.com/vivianokose/nexaops-operations-lab).
