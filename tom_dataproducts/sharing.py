
def share_data_with_hermes(share_destination, form_data, product_id=None, target_id=None, selected_data=None):
    # Query relevant Reduced Datums Queryset
    accepted_data_types = ['photometry']
    if product_id:
        product = DataProduct.objects.get(pk=product_id)
        reduced_datums = ReducedDatum.objects.filter(data_product=product)
    elif selected_data:
        reduced_datums = ReducedDatum.objects.filter(pk__in=selected_data)
    elif target_id:
        target = Target.objects.get(pk=target_id)
        data_type = form_data['data_type']
        reduced_datums = ReducedDatum.objects.filter(target=target, data_type=data_type)
    else:
        reduced_datums = ReducedDatum.objects.none()

    reduced_datums.filter(data_type__in=accepted_data_types)

    # Build and submit hermes table from Reduced Datums
    hermes_topic = share_destination.split(':')[1]
    destination = share_destination.split(':')[0]
    message_info = BuildHermesMessage(title=form_data['share_title'],
                                      submitter=form_data['submitter'],
                                      authors=form_data['share_authors'],
                                      message=form_data['share_message'],
                                      topic=hermes_topic
                                      )
    # Run ReducedDatums Queryset through sharing protocols to make sure they are safe to share.
    filtered_reduced_datums = get_share_safe_datums(destination, reduced_datums, topic=hermes_topic)
    if filtered_reduced_datums.count() > 0:
        response = publish_photometry_to_hermes(message_info, filtered_reduced_datums)
    else:
        def response():
            def json():
                return {'message': f'No Data to share. (Check sharing Protocol, note that data types must be in '
                                   f'{accepted_data_types})'}
    return response


def share_data_with_tom(destination, datums, product=None):
    """
    When sharing a DataProduct with another TOM we likely want to share the data product itself and let the other
    TOM process it rather than share the Reduced Datums
    :param destination: name of destination tom in settings.DATA_SHARING
    :param datums: Queryset of ReducedDatum Instances
    :param product: DataProduct model instance
    :return:
    """
    try:
        destination_tom_base_url = settings.DATA_SHARING[destination]['BASE_URL']
        username = settings.DATA_SHARING[destination]['USERNAME']
        password = settings.DATA_SHARING[destination]['PASSWORD']
    except KeyError as err:
        raise ImproperlyConfigured(f'Check DATA_SHARING configuration for {destination}: Key {err} not found.')
    auth = (username, password)
    headers = {'Media-Type': 'application/json'}
    target = product.target
    serialized_target_data = TargetSerializer(target).data
    targets_url = destination_tom_base_url + 'api/targets/'
    # TODO: Make sure aliases are checked before creating new target
    # Attempt to create Target in Destination TOM
    # response = requests.post(targets_url, headers=headers, auth=auth, data=serialized_target_data)
    # try:
    #     target_response = response.json()
    #     destination_target_id = target_response['id']
    # except KeyError:
    #     # If Target already exists at destination, find ID
    #     response = requests.get(targets_url, headers=headers, auth=auth, data=serialized_target_data)
    #     target_response = response.json()
    #     destination_target_id = target_response['results'][0]['id']

    print(serialized_target_data)

    response = requests.get(f'{targets_url}?name={target.name}', headers=headers, auth=auth)
    target_response = response.json()
    if target_response['results']:
        destination_target_id = target_response['results'][0]['id']
    else:
        return response
    print("------------------------")
    print(target_response)
    serialized_dataproduct_data = DataProductSerializer(product).data
    serialized_dataproduct_data['target'] = destination_target_id
    dataproducts_url = destination_tom_base_url + 'api/dataproducts/'
    # TODO: this should be updated when tom_dataproducts is updated to use django.core.storage
    dataproduct_filename = os.path.join(settings.MEDIA_ROOT, product.data.name)
    # Save DataProduct in Destination TOM
    # with open(dataproduct_filename, 'rb') as dataproduct_filep:
    #     files = {'file': (product.data.name, dataproduct_filep, 'text/csv')}
    #     headers = {'Media-Type': 'multipart/form-data'}
    #     response = requests.post(dataproducts_url, data=serialized_dataproduct_data, files=files,
    #                              headers=headers, auth=auth)
    return response


def check_for_share_safe_datums():
    return


def check_for_save_safe_datums():
    return
