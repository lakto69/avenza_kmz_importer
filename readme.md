<html>
<body>
<h3>AvenzaKMLImporter</h3>

<h3>What motivated me to create this plugin:</h3>

<p>Only after plotting more than a hundred points, in the field, in the <a href="https://store.avenza.com/">Avenza Maps</a>, taking care to use an icon style to represent each type of point we were plotting, and trying to import them into <a href="https://qgis.org/">QGIS</a> did we realize that we were not it was possible to import the features while preserving the symbology style used in Avenza (or another equivalent, which could group the points by type of symbology). And so, we ended up losing a very important dimension of information that we used in that app: the symbolism of the dot.
</p>
<p>So, I decided to create this plugin.</p>

<p>As it was created to solve this problem we had while using Avenza, and as the KML format is quite extensive, <u>we focused on only meeting the formatting used by Avenza</u> (<b>in the year 2023</b>).</p>

<p>In practice, I've seen that some files created by <a href="https://www.google.com/intl/pt-BR/earth/about/">Google Earth</a> are not importable by this plugin.</p>

<p>If anyone is interested in expanding the list of applications supported by this plugin, fell free to fork this project and make their own implementation.</p>
<h3>What this plugin do:</h3>
<p>It imports a KML or KMZ file that the user chooses and adds all the features from that file to QGIS as follows:
    <ol style="list-style-type: lower-latin">
        <li>Adds a group with the name indicated in the plugin's Group field (When a file is uploaded, this field is filled with its name. If you want to change it, do so after choosing the file to be imported).</li>
        <li>Within this group, as many subgroups as there are layers present in the imported file will be created. And they will be named with the same name as those found in the imported file.</li>
        <li>Within each subgroup, a layer will be created for each type of feature found: <b>point</b>, <b>line</b> and <b>polygon</b>. And all features in the file layer will be organized within the respective layer (point, line or polygon) categorized by the style adopted in Avenza.</li>
        <li>If a point-type feature is found, the symbology used will be with icons similar to those that Avenza currently makes available in its free version (October 2023)</li>
        <li>If a Track type feature is found, this feature will be added to two QGIS layers: 
            <ol style="list-style-type: lower-roman">
                <li>a points layer, containing all the information for each point (speed, horizontal and vertical accuracy, etc.) and represented by target-shaped icons</li>
                <li>and another line, represented using the symbology that was used in the Avenza.</li>
            </ol></li>
    </ol>
</p>
<p>Depending on the user checking/unchecking the 'Expand All Features' checkbox, the group will be added to QGIS fully expanded or completely collapsed.</p>
<p>The plugin saves the folder corresponding to the last valid file choice in its settings, to be used when choosing a new file and, when closed, it saves the state of the 'Expand All Features' checkbox, the size and location of the window</p>
<p><b>This plugin was created during leisure moments, as a challenge. So, it is possible that, in the near future, this project will not continue.</b></p>

</body>
</html>
